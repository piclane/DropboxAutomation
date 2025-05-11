import logging
import os
import sys

from settings import validate_env_vars

logger = logging.getLogger(__name__)

def main():
    # コマンドライン引数をチェック
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        # ローカルファイルモード
        local_file_path = sys.argv[1]
        if not validate_env_vars(for_dropbox=False):
            sys.exit(1)

        logger.info(f"Running in local file mode for: {local_file_path}")
        import processer_local
        processer_local.process(local_file_path)
    else:
        # FastAPI Webhook モード
        if not validate_env_vars(for_dropbox=True):
            sys.exit(1)

        import processor_dropbox
        processor_dropbox.start_server()

if __name__ == '__main__':
    main()
