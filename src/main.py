import argparse
import logging
import os
import sys

from settings import validate_env_vars

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Dropbox PDF Automation Tool')
    parser.add_argument('pdf_path', nargs='?', help='Path to the PDF file to process (local mode)')
    parser.add_argument('--publish', action='store_true', help='RabbitMQ に解析結果を publish する')
    parser.add_argument('--icloud', action='store_true', help='schedule_to_icloud 経由で iCloud に登録する')

    args = parser.parse_args()

    # コマンドライン引数をチェック
    if args.pdf_path and os.path.isfile(args.pdf_path):
        # ローカルファイルモード
        local_file_path = args.pdf_path
        if not validate_env_vars(for_dropbox=False):
            sys.exit(1)

        logger.info(f"Running in local file mode for: {local_file_path}")
        import processer_local
        processer_local.process(local_file_path, publish=args.publish, icloud=args.icloud)
    elif args.pdf_path:
        # 引数はあるがファイルではない場合（ヘルプ以外で無効なパスが渡された場合）
        logger.error(f"File not found: {args.pdf_path}")
        parser.print_help()
        sys.exit(1)
    else:
        # FastAPI Webhook モード
        if not validate_env_vars(for_dropbox=True):
            sys.exit(1)

        import processor_dropbox
        processor_dropbox.start_server()

if __name__ == '__main__':
    main()
