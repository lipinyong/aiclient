import os
import smtplib
import markdown
import json
import traceback
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import logging

# 配置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

async def get(request, config_manager=None):
    """
    GET /api/mail/send - 不支持 GET 请求，必须使用 POST
    """
    return {
        "success": False,
        "error": "邮件发送 API 不支持 GET 请求，请使用 POST 方法并在请求体中提供参数",
        "message": "Method Not Allowed: Please use POST method with JSON body"
    }

async def handler(request, config_manager=None):
    """
    处理邮件发送请求，根据请求方法调用相应的处理函数
    """
    if request.method == "GET":
        return await get(request, config_manager)
    elif request.method == "POST":
        return await post(request, config_manager)
    else:
        return {
            "success": False,
            "error": f"不支持 {request.method} 请求方法",
            "message": f"Method Not Allowed: {request.method}"
        }

# 为了兼容 execute_py_module 函数，添加 handle 别名
handle = handler
main = handler

async def post(request, config_manager=None):
    """
    POST /api/mail/send - 发送邮件
    
    请求体 (JSON):
    {
        "subject": "邮件主题",
        "content": "邮件内容（支持 Markdown 格式）",
        "to": "recipient@example.com" 或 ["email1@example.com", "email2@example.com"],
        "cc": "cc@example.com" 或 ["cc1@example.com", "cc2@example.com"] (可选),
        "bcc": "bcc@example.com" 或 ["bcc1@example.com", "bcc2@example.com"] (可选),
        "content_type": "markdown" 或 "html" 或 "plain" (可选，默认 markdown),
        "send_separately": true 或 false (可选，默认 false，是否单独发送给每个收件人)
    }
    
    返回:
    {
        "success": true,
        "message": "邮件发送成功",
        "data": {
            "recipients": ["email1@example.com"],
            "subject": "邮件主题"
        }
    }
    """
    try:
        # 读取环境变量中的 SMTP 配置
        smtp_host = "mail.lubanlou.com"
        smtp_port = 18025
        smtp_user = "gvsun@lubanlou.com"
        smtp_password = "gengshang@123"
        
        # 验证 SMTP 配置
        if not smtp_host or not smtp_user or not smtp_password:
            return {
                "success": False,
                "error": "SMTP 配置不完整，请检查环境变量：SMTP_HOST, SMTP_USER, SMTP_PASSWORD"
            }
        
        # 类型断言：经过验证后，这些值不会是 None
        smtp_host_str: str = smtp_host
        smtp_user_str: str = smtp_user
        smtp_password_str: str = smtp_password
        
        # 解析请求体
        body = await request.json()
        
        subject = body.get("subject", "").strip()
        content = body.get("content", "").strip()
        to = body.get("to")
        cc = body.get("cc")
        bcc = body.get("bcc")
        content_type = body.get("content_type", "markdown").lower()
        send_separately = body.get("send_separately", False)
        
        # 验证必填字段
        if not subject:
            return {
                "success": False,
                "error": "缺少必填字段: subject（邮件主题）"
            }
        
        if not content:
            return {
                "success": False,
                "error": "缺少必填字段: content（邮件内容）"
            }
        
        if not to:
            return {
                "success": False,
                "error": "缺少必填字段: to（收件人邮箱）"
            }
        
        # 处理收件人列表（To）
        def parse_email_list(email_input):
            """解析邮箱列表，返回邮箱数组"""
            if not email_input:
                return []
            
            # 如果是字符串，尝试解析为 JSON 或按逗号分隔
            if isinstance(email_input, str):
                email_input = email_input.strip()
                
                # 尝试 JSON 解析（处理流水线传递的 JSON 字符串）
                if email_input.startswith('[') and email_input.endswith(']'):
                    try:
                        parsed = json.loads(email_input)
                        if isinstance(parsed, list):
                            logger.info(f"JSON 解析成功: {email_input} -> {parsed}")
                            # 去除所有空白字符（包括换行符、制表符等）
                            cleaned = []
                            for email in parsed:
                                if email:
                                    # 去除所有空白字符
                                    clean_email = ''.join(email.split())
                                    if clean_email:
                                        cleaned.append(clean_email)
                            return cleaned
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 解析失败: {email_input}, 错误: {e}")
                
                # 按逗号分隔
                if ',' in email_input:
                    return [''.join(email.split()) for email in email_input.split(',') if email.strip()]
                
                # 单个邮箱（去除所有空白字符）
                return [''.join(email_input.split())]
            
            # 如果已经是数组
            elif isinstance(email_input, list):
                cleaned = []
                for email in email_input:
                    if email:
                        # 如果是字符串，去除所有空白字符
                        if isinstance(email, str):
                            clean_email = ''.join(email.split())
                            if clean_email:
                                cleaned.append(clean_email)
                        else:
                            cleaned.append(str(email))
                return cleaned
            
            return []
        
        # 记录原始输入（用于调试）
        logger.info(f"邮件发送请求 - 主题: {subject}")
        logger.info(f"收件人原始数据 (to): type={type(to).__name__}, value={to}")
        logger.info(f"抄送原始数据 (cc): type={type(cc).__name__}, value={cc}")
        logger.info(f"密送原始数据 (bcc): type={type(bcc).__name__}, value={bcc}")
        
        recipients = parse_email_list(to)
        cc_recipients = parse_email_list(cc)
        bcc_recipients = parse_email_list(bcc)
        
        # 记录解析结果
        logger.info(f"解析后的收件人 (to): {recipients}")
        logger.info(f"解析后的抄送 (cc): {cc_recipients}")
        logger.info(f"解析后的密送 (bcc): {bcc_recipients}")
        
        # 验证邮箱格式
        recipients = [email for email in recipients if '@' in email]
        cc_recipients = [email for email in cc_recipients if '@' in email]
        bcc_recipients = [email for email in bcc_recipients if '@' in email]
        
        if not recipients:
            return {
                "success": False,
                "error": "未找到有效的收件人邮箱（To）"
            }
        
        # 所有收件人（用于实际发送）
        all_recipients = recipients + cc_recipients + bcc_recipients
        
        # 根据内容类型处理邮件内容
        styled_html = ""  # 初始化变量
        if content_type == "markdown":
            # 将 Markdown 转换为 HTML
            html_content = markdown.markdown(
                content,
                extensions=['tables', 'fenced_code', 'codehilite']
            )
            styled_html = f"""
            <html>
              <head>
                <meta charset="utf-8">
                <style>
                  body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
                  table {{ border-collapse: collapse; margin: 1em 0; width: 100%; }}
                  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
                  th {{ background-color: #f5f5f5; font-weight: bold; }}
                  h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                  h2 {{ color: #34495e; }}
                  a {{ color: #3498db; text-decoration: none; }}
                  a:hover {{ text-decoration: underline; }}
                  code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
                  pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                </style>
              </head>
              <body>
                {html_content}
              </body>
            </html>
            """
        
        # 发送邮件的辅助函数
        def send_email(to_list, cc_list=None, bcc_list=None, hide_recipients=False):
            """
            发送邮件
            
            Args:
                to_list: 收件人列表
                cc_list: 抄送列表（可选）
                bcc_list: 密送列表（可选）
                hide_recipients: 是否隐藏其他收件人（单独发送模式）
            """
            # 创建新的邮件消息（每次发送都需要新的实例）
            if content_type == "markdown":
                msg = MIMEText(styled_html, 'html', 'utf-8')
            elif content_type == "html":
                msg = MIMEText(content, 'html', 'utf-8')
            else:
                msg = MIMEText(content, 'plain', 'utf-8')
            
            sender_name = os.getenv("SMTP_FROM_NAME", "系统通知")
            msg['From'] = formataddr((
                Header(sender_name, 'utf-8').encode(),
                smtp_user_str
            ))
            msg['To'] = Header(", ".join(to_list), 'utf-8').encode()
            
            # 只在非单独发送模式下添加CC头（保护BCC隐私）
            if cc_list and not hide_recipients:
                msg['Cc'] = Header(", ".join(cc_list), 'utf-8').encode()
            
            # 注意：永远不要添加 BCC 头，BCC 收件人只在 sendmail 中指定
            msg['Subject'] = Header(subject, 'utf-8')
            
            # 实际收件人列表（包括BCC，但不出现在邮件头中）
            actual_recipients = to_list[:]
            if cc_list and not hide_recipients:
                actual_recipients.extend(cc_list)
            if bcc_list:
                actual_recipients.extend(bcc_list)
            
            # 记录发送详情
            logger.info(f"发送邮件 - To: {to_list}, 实际收件人列表: {actual_recipients}, hide_recipients: {hide_recipients}")
            
            # 根据端口选择连接方式
            if smtp_port == 465:
                # 使用 SSL 连接（端口465需要SSL）
                logger.info(f"使用 SMTP_SSL 连接到 {smtp_host_str}:{smtp_port}")
                with smtplib.SMTP_SSL(smtp_host_str, smtp_port, timeout=30) as server:
                    server.login(smtp_user_str, smtp_password_str)
                    server.sendmail(smtp_user_str, actual_recipients, msg.as_string())
                    logger.info(f"邮件发送成功 - 收件人: {actual_recipients}")
            else:
                # 使用普通 SMTP 或 STARTTLS（端口25/587）
                logger.info(f"使用 SMTP 连接到 {smtp_host_str}:{smtp_port}")
                with smtplib.SMTP(smtp_host_str, smtp_port, timeout=30) as server:
                    if smtp_port == 587:
                        server.starttls()
                        logger.info("STARTTLS 升级成功")
                    server.login(smtp_user_str, smtp_password_str)
                    logger.info("SMTP 登录成功")
                    server.sendmail(smtp_user_str, actual_recipients, msg.as_string())
                    logger.info(f"邮件发送成功 - 收件人: {actual_recipients}")
        
        # 发送邮件
        logger.info(f"准备发送邮件 - 单独发送: {send_separately}, To收件人数: {len(recipients)}, CC数: {len(cc_recipients)}, BCC数: {len(bcc_recipients)}")
        
        try:
            sent_count = 0
            
            if send_separately:
                # 单独发送给每个To收件人（每人收到独立的邮件，看不到其他人）
                for recipient in recipients:
                    send_email([recipient], None, None, hide_recipients=True)
                    sent_count += 1
                
                # 如果有CC收件人，也单独发送给他们
                for cc_recipient in cc_recipients:
                    send_email([cc_recipient], None, None, hide_recipients=True)
                    sent_count += 1
                
                # 如果有BCC收件人，也单独发送给他们
                for bcc_recipient in bcc_recipients:
                    send_email([bcc_recipient], None, None, hide_recipients=True)
                    sent_count += 1
                
                logger.info(f"邮件单独发送成功：主题={subject}, 总发送数={sent_count}")
                success_message = f"邮件已单独发送给 {sent_count} 个收件人"
            else:
                # 批量发送（所有To和CC收件人可见，BCC收件人隐藏）
                send_email(recipients, cc_recipients or None, bcc_recipients or None, hide_recipients=False)
                sent_count = len(all_recipients)
                
                logger.info(f"邮件批量发送成功：主题={subject}, To={len(recipients)}, CC={len(cc_recipients)}, BCC={len(bcc_recipients)}")
                success_message = f"邮件发送成功！共 {len(recipients)} 个收件人"
                if cc_recipients:
                    success_message += f"，{len(cc_recipients)} 个抄送"
                if bcc_recipients:
                    success_message += f"，{len(bcc_recipients)} 个密送"
            
            return {
                "success": True,
                "message": success_message,
                "data": {
                    "to": recipients,
                    "cc": cc_recipients,
                    "bcc": bcc_recipients,
                    "subject": subject,
                    "content_type": content_type,
                    "send_separately": send_separately,
                    "total_sent": sent_count
                }
            }
            
        except smtplib.SMTPAuthenticationError as e:
            error_detail = traceback.format_exc()
            logger.error(f"SMTP 认证失败: {str(e)}")
            logger.error(f"错误详情:\n{error_detail}")
            return {
                "success": False,
                "error": f"SMTP 认证失败，请检查用户名和密码: {str(e)}"
            }
        except smtplib.SMTPException as e:
            error_detail = traceback.format_exc()
            logger.error(f"邮件发送失败: {str(e)}")
            logger.error(f"错误详情:\n{error_detail}")
            return {
                "success": False,
                "error": f"邮件发送失败: {str(e)}"
            }
        
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"处理邮件发送请求时发生错误: {str(e)}")
        logger.error(f"错误详情:\n{error_detail}")
        return {
            "success": False,
            "error": f"服务器错误: {str(e)}"
        }
