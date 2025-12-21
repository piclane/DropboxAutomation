import html

def summarize_to_html(analysis: dict, dest_path: str) -> None:
    """
    分析結果をHTMLにまとめて保存する。
    
    Args:
        analysis (dict): 分析結果データ
            - date: YYYYMMDD
            - title: タイトル
            - summary: 要約
            - todo: [{"action": "...", "deadline": "..."}]
        dest_path (str): 保存先のパス
    """
    date = analysis.get("date", "")
    if len(date) == 8:
        formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    else:
        formatted_date = date

    title = html.escape(analysis.get("title", "No Title"))
    summary_raw = analysis.get("summary", "")
    summary_lines = summary_raw.split('\n')
    
    # より堅牢な要約のHTML変換
    summary_html = ""
    in_list = False
    for line in summary_lines:
        line = line.strip()
        if not line:
            if in_list:
                summary_html += "</ul>"
                in_list = False
            summary_html += "<br>"
            continue
        
        if line.startswith('・') or line.startswith('- '):
            if not in_list:
                summary_html += "<ul>"
                in_list = True
            summary_html += f"<li>{html.escape(line[1:].strip())}</li>"
        else:
            if in_list:
                summary_html += "</ul>"
                in_list = False
            summary_html += f"<p>{html.escape(line)}</p>"
    if in_list:
        summary_html += "</ul>"

    todo_html = ""
    todo_list = analysis.get("todo", [])
    if todo_list:
        todo_html = "<table><thead><tr><th>Action</th><th>Deadline</th></tr></thead><tbody>"
        for item in todo_list:
            action = html.escape(item.get("action", ""))
            deadline = html.escape(str(item.get("deadline") or "-"))
            todo_html += f"<tr><td>{action}</td><td>{deadline}</td></tr>"
        todo_html += "</tbody></table>"
    else:
        todo_html = "<p>TODOはありません。</p>"

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', 'Hiragino Sans', Meiryo, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .container {{
            background-color: #fff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        header {{
            border-bottom: 2px solid #007bff;
            margin-bottom: 20px;
            padding-bottom: 10px;
        }}
        .date {{
            color: #666;
            font-size: 0.9em;
            text-align: right;
        }}
        h1 {{
            margin: 10px 0;
            color: #007bff;
            font-size: 1.5em;
        }}
        section {{
            margin-bottom: 30px;
        }}
        h2 {{
            font-size: 1.2em;
            border-left: 4px solid #007bff;
            padding-left: 10px;
            margin-bottom: 15px;
            color: #333;
        }}
        .summary p {{
            margin-bottom: 10px;
        }}
        .summary ul {{
            margin-bottom: 15px;
            padding-left: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        @media (max-width: 600px) {{
            body {{
                padding: 10px;
            }}
            .container {{
                padding: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="date">作成日: {formatted_date}</div>
            <h1>{title}</h1>
        </header>
        
        <section class="summary">
            <h2>要約</h2>
            {summary_html}
        </section>
        
        <section class="todo">
            <h2>TODOリスト</h2>
            {todo_html}
        </section>
    </div>
</body>
</html>
"""
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(html_content)
