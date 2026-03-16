import unittest
from unittest.mock import MagicMock, patch, call
import pika
import subprocess
from schedule_to_icloud.src.utils.rabbitmq_consumer import RabbitMQConsumer

class TestRabbitMQConsumer(unittest.TestCase):
    def setUp(self):
        self.uri = "amqp://user:pass@host:5672/vhost/exchange"

    def test_parse_uri_amqp(self):
        exchange, params = RabbitMQConsumer._parse_uri(self.uri)
        self.assertEqual(exchange, "exchange")
        self.assertEqual(params.host, "host")
        self.assertEqual(params.port, 5672)
        self.assertEqual(params.virtual_host, "vhost")
        self.assertEqual(params.credentials.username, "user")
        self.assertEqual(params.credentials.password, "pass")
        self.assertIsNone(params.ssl_options)

    def test_parse_uri_amqps(self):
        uri = "amqps://user:pass@host:5671/vhost/exchange"
        exchange, params = RabbitMQConsumer._parse_uri(uri)
        self.assertEqual(exchange, "exchange")
        self.assertEqual(params.port, 5671)
        self.assertIsNotNone(params.ssl_options)

    def test_parse_uri_invalid_scheme(self):
        uri = "http://host/vhost/exchange"
        with self.assertRaises(ValueError) as cm:
            RabbitMQConsumer._parse_uri(uri)
        self.assertIn("Unsupported scheme", str(cm.exception))

    def test_parse_uri_missing_path(self):
        uri = "amqp://host/exchange"
        with self.assertRaises(ValueError) as cm:
            RabbitMQConsumer._parse_uri(uri)
        self.assertIn("URI path must be", str(cm.exception))

    @patch("subprocess.run")
    def test_get_hardware_uuid_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout='    "IOPlatformUUID" = "TEST-UUID-1234"\n',
            returncode=0
        )
        uuid = RabbitMQConsumer._get_hardware_uuid()
        self.assertEqual(uuid, "TEST-UUID-1234")
        mock_run.assert_called_once_with(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
        )

    @patch("subprocess.run")
    def test_get_hardware_uuid_failure(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        with self.assertRaises(RuntimeError):
            RabbitMQConsumer._get_hardware_uuid()

    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer._get_hardware_uuid")
    def test_get_persistent_queue_name(self, mock_get_uuid):
        mock_get_uuid.return_value = "TEST-UUID"
        queue_name = RabbitMQConsumer.get_persistent_queue_name()
        self.assertEqual(queue_name, "s2ic_TEST-UUID")

    @patch("pika.BlockingConnection")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer._exists_persistent_queue")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer.get_persistent_queue_name")
    def test_connect_with_persistent_queue(self, mock_get_qname, mock_exists, mock_blocking_conn):
        mock_get_qname.return_value = "persistent_q"
        mock_exists.return_value = True

        mock_conn = MagicMock()
        mock_channel = MagicMock()
        mock_blocking_conn.return_value = mock_conn
        mock_conn.channel.return_value = mock_channel

        consumer = RabbitMQConsumer(self.uri)

        self.assertEqual(consumer._queue_name, "persistent_q")
        mock_channel.exchange_declare.assert_called_once()
        mock_channel.queue_declare.assert_not_called() # _exists_persistent_queue uses passive=True but it's mocked here

    @patch("pika.BlockingConnection")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer._exists_persistent_queue")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer.get_persistent_queue_name")
    def test_connect_with_temporary_queue(self, mock_get_qname, mock_exists, mock_blocking_conn):
        mock_get_qname.return_value = "persistent_q"
        mock_exists.return_value = False

        mock_conn = MagicMock()
        mock_channel = MagicMock()
        mock_blocking_conn.return_value = mock_conn
        mock_conn.channel.return_value = mock_channel

        mock_declare_result = MagicMock()
        mock_declare_result.method.queue = "tmp_q"
        mock_channel.queue_declare.return_value = mock_declare_result

        consumer = RabbitMQConsumer(self.uri)

        self.assertEqual(consumer._queue_name, "tmp_q")
        mock_channel.queue_declare.assert_called_once_with(queue='', exclusive=True)
        mock_channel.queue_bind.assert_called_with(exchange="exchange", queue="tmp_q")

    @patch("pika.BlockingConnection")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer._connect")
    @patch("time.sleep")
    def test_consume_exponential_backoff(self, mock_sleep, mock_connect, mock_blocking_conn):
        consumer = RabbitMQConsumer(self.uri)
        consumer._channel = MagicMock()
        consumer._connection = MagicMock()
        consumer._connection.is_closed = False

        # side_effect to test multiple retries then success then another failure
        def side_effect(*args, **kwargs):
            if side_effect.count == 0:
                side_effect.count += 1
                raise pika.exceptions.AMQPConnectionError("Err 1")
            elif side_effect.count == 1:
                side_effect.count += 1
                raise pika.exceptions.AMQPConnectionError("Err 2")
            elif side_effect.count == 2:
                side_effect.count += 1
                return # Success
            elif side_effect.count == 3:
                side_effect.count += 1
                raise pika.exceptions.AMQPConnectionError("Err 3")
            else:
                raise Exception("Stop Loop")

        side_effect.count = 0
        consumer._channel.start_consuming.side_effect = side_effect

        callback = MagicMock()
        with self.assertRaises(Exception) as cm:
            consumer.consume(callback)
        self.assertEqual(str(cm.exception), "Stop Loop")

        # Check sleep calls
        # 1. Err 1: 5s
        # 2. Err 2: 10s
        # 3. Success: (no sleep)
        # 4. Err 3: 5s (reset)
        mock_sleep.assert_has_calls([call(5), call(10), call(5)])

    @patch("pika.BlockingConnection")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer._connect")
    @patch("time.sleep")
    def test_consume_max_backoff(self, mock_sleep, mock_connect, mock_blocking_conn):
        consumer = RabbitMQConsumer(self.uri)
        consumer._channel = MagicMock()
        consumer._connection = MagicMock()
        consumer._connection.is_closed = False

        # Set retry_delay high
        def side_effect(*args, **kwargs):
            raise pika.exceptions.AMQPConnectionError("Continuous Error")

        consumer._channel.start_consuming.side_effect = side_effect

        # We need to stop the loop, so we'll mock sleep to raise exception after some calls
        side_effect.call_count = 0
        def sleep_side_effect(seconds):
            side_effect.call_count += 1
            if seconds >= 300:
                raise Exception("Max Reached")

        mock_sleep.side_effect = sleep_side_effect

        with self.assertRaises(Exception) as cm:
            consumer.consume(MagicMock())
        self.assertEqual(str(cm.exception), "Max Reached")

        # Expected sequence: 5, 10, 20, 40, 80, 160, 300
        expected_sleeps = [5, 10, 20, 40, 80, 160, 300]
        actual_sleeps = [c[0][0] for c in mock_sleep.call_args_list]
        self.assertEqual(actual_sleeps, expected_sleeps)

    @patch("pika.BlockingConnection")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer._connect")
    @patch("time.sleep")
    def test_consume_unexpected_error_limit(self, mock_sleep, mock_connect, mock_blocking_conn):
        consumer = RabbitMQConsumer(self.uri)
        consumer._channel = MagicMock()
        consumer._connection = MagicMock()
        consumer._connection.is_closed = False

        consumer._channel.start_consuming.side_effect = Exception("Unexpected")

        with self.assertRaises(Exception) as cm:
            consumer.consume(MagicMock())
        self.assertEqual(str(cm.exception), "Unexpected")

        # error_count reached 10
        self.assertEqual(consumer._channel.start_consuming.call_count, 10)
        self.assertEqual(mock_sleep.call_count, 9) # Sleep before 10th attempt

    @patch("pika.BlockingConnection")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer._connect")
    def test_install_persistent_queue(self, mock_connect, mock_blocking_conn):
        consumer = RabbitMQConsumer(self.uri)
        consumer._channel = MagicMock()

        # Already exists
        with patch.object(consumer, "_exists_persistent_queue", return_value=True):
            consumer.install_persistent_queue("test_q")
            consumer._channel.queue_declare.assert_not_called()

        # Not exists
        with patch.object(consumer, "_exists_persistent_queue", return_value=False):
            consumer.install_persistent_queue("test_q")
            consumer._channel.queue_declare.assert_called_once_with(
                queue="test_q", durable=True, exclusive=False, auto_delete=False
            )
            consumer._channel.queue_bind.assert_called_with(exchange="exchange", queue="test_q")

    @patch("pika.BlockingConnection")
    @patch("schedule_to_icloud.src.utils.rabbitmq_consumer.RabbitMQConsumer._connect")
    def test_uninstall_persistent_queue(self, mock_connect, mock_blocking_conn):
        consumer = RabbitMQConsumer(self.uri)
        consumer._channel = MagicMock()

        # Not exists
        with patch.object(consumer, "_exists_persistent_queue", return_value=False):
            consumer.uninstall_persistent_queue("test_q")
            consumer._channel.queue_delete.assert_not_called()

        # Exists
        with patch.object(consumer, "_exists_persistent_queue", return_value=True):
            consumer.uninstall_persistent_queue("test_q")
            consumer._channel.queue_unbind.assert_called_with(queue="test_q", exchange="exchange")
            consumer._channel.queue_delete.assert_called_once_with(queue="test_q")

if __name__ == "__main__":
    unittest.main()
