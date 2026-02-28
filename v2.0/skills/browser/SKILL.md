---
name: browser
description: 在默认浏览器中打开 URL；或在后台无头浏览指定 URL，等待 JavaScript 渲染完成后通过 document.body.innerText 读取完整页面纯文本。用户说「读取网页」「抓取网页」并给出 URL 时，必须直接调用 browser_fetch_content，不要写脚本。
triggers: [浏览器, browser, 打开网页, 打开链接, 打开网址, 打开url, 在浏览器打开, 读取网页, 抓取网页, 页面内容, 网页内容]
---

# 浏览器技能

当用户要求**在浏览器中打开链接**、**读取/抓取某 URL 的页面内容**（含 JS 渲染后的纯文本）时使用本技能。

## 使用场景

- **打开链接**：用户提供 URL，要求用默认浏览器打开 → 使用 **browser_open**。
- **读取页面内容**：用户说「读取网页」「抓取网页」「把这个网页的内容抓下来」并给出 URL 时，**必须直接调用 browser_fetch_content**，不要用 run_script/run_shell 编写或执行 Python/Selenium/requests 等爬虫脚本。工具会在后台无头打开页面，等待 JS 渲染后通过 **document.body.innerText** 返回纯文本。

## 行为规范

1. **【必须】抓取/读取网页时只调用 browser_fetch_content**，禁止调用 run_script、run_shell 或编写任何 Python/Selenium/requests 脚本。调用成功后**在回复中只展示抓取到的内容**：可对 content 做分段、排版、整理，但**不要**做内容特点分析、要点归纳、评价或其它解读，仅输出整理后的抓取信息本身。
2. 仅需“打开给用户看”时用 **browser_open**。
3. 需要“拿到页面内容”时**只调用 browser_fetch_content**，回复中**只呈现整理后的 content 正文**，不添加“该页面特点”“从内容可以看出”等分析性表述。
4. URL 未带协议时自动补全为 `https://`。

## 说明

- **browser_fetch_content** 使用 Playwright 无头 Chromium，返回 **document.body.innerText** 的纯文本。需安装：`pip install playwright` 后执行 `playwright install chromium`。默认 networkidle 后再等待 2 秒（extra_wait_ms）以应对 SPA 延迟渲染；若内容仍不全可增大 timeout_ms 或 extra_wait_ms。

## 推荐提问（可直接复制到对话中使用）

以下提问会触发本技能并调用 browser_fetch_content 抓取页面纯文本，避免误走“写脚本”：

- **用浏览器技能抓取这个页面的内容：** https://aiclip.lubanlou.com/shared/a2331112-fe48-4d16-b767-82f8b8d35ea9
- **调用 browser_fetch_content 读取该 URL 的正文：** https://aiclip.lubanlou.com/shared/a2331112-fe48-4d16-b767-82f8b8d35ea9
- **抓取网页内容（不要写脚本，用 browser 工具）：** https://aiclip.lubanlou.com/shared/a2331112-fe48-4d16-b767-82f8b8d35ea9
- **读取该链接的页面文字并总结：** https://aiclip.lubanlou.com/shared/a2331112-fe48-4d16-b767-82f8b8d35ea9

若仍被误匹配为 pdf-reader 或去写脚本，可显式指定技能：`--skills browser` 后再提问。
