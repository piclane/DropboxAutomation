import argparse
import logging
import os
import sys

from settings import validate_env_vars

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Dropbox PDF Automation Tool')
    parser.add_argument('pdf_path', nargs='?', help='Path to the PDF file to process (local mode)')
    
    args = parser.parse_args()

    # コマンドライン引数をチェック
    if args.pdf_path and os.path.isfile(args.pdf_path):
        # ローカルファイルモード
        local_file_path = args.pdf_path
        if not validate_env_vars(for_dropbox=False):
            sys.exit(1)

        logger.info(f"Running in local file mode for: {local_file_path}")
        import processer_local
        processer_local.process(local_file_path)
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
