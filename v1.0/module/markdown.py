import markdown
from markdown.extensions import fenced_code, tables, toc
import logging

logger = logging.getLogger(__name__)


class MarkdownRenderer:
    def __init__(self):
        self.md = markdown.Markdown(
            extensions=[
                'fenced_code',
                'tables',
                'toc',
                'meta',
                'nl2br',
                'sane_lists'
            ],
            extension_configs={
                'toc': {
                    'permalink': True,
                    'toc_depth': '2-4'
                }
            }
        )
    
    def render(self, content: str, base_path: str = "") -> str:
        self.md.reset()
        html_content = self.md.convert(content)
        
        template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Node MCP</title>
    <script>
        window.BASE_PATH = (function() {{
            const path = window.location.pathname;
            const parts = path.split('/');
            let basePath = '';
            for (let i = 1; i < parts.length - 1; i++) {{
                if (parts[i] && !parts[i].includes('.')) {{
                    if (parts.slice(i).join('/').includes('web') || 
                        ['aichat', 'xmgl', 'login', 'report', 'api'].includes(parts[i])) {{
                        break;
                    }}
                    basePath += '/' + parts[i];
                }} else {{
                    break;
                }}
            }}
            return basePath;
        }})();
    </script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}
        h1 {{ font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.25em; }}
        p {{ margin-bottom: 16px; }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        code {{
            background-color: rgba(27,31,35,0.05);
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: 85%;
        }}
        pre {{
            background-color: #f6f8fa;
            padding: 16px;
            overflow: auto;
            border-radius: 6px;
            margin-bottom: 16px;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }}
        table th, table td {{
            border: 1px solid #dfe2e5;
            padding: 6px 13px;
        }}
        table tr:nth-child(2n) {{
            background-color: #f6f8fa;
        }}
        blockquote {{
            border-left: 4px solid #dfe2e5;
            padding-left: 16px;
            color: #6a737d;
            margin-bottom: 16px;
        }}
        ul, ol {{
            padding-left: 2em;
            margin-bottom: 16px;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_content}
    </div>
</body>
</html>'''
        return template
    
    def render_content_only(self, content: str) -> str:
        self.md.reset()
        return self.md.convert(content)


markdown_renderer = MarkdownRenderer()
