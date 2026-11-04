# Chrome Web Store listing

## Title

Local Browser: AI Browser Automation

## Summary

Let your AI agent use your existing Chrome tabs and logins. Read pages, fill forms and take screenshots through MCP.

## Description

Put your AI agent to work in the Chrome browser you already use.

Local Browser connects your agent to your existing tabs and signed-in accounts. Ask it to read a page, fill a form, click a button or capture a screenshot, without moving your work to a separate browser or signing in again.

USE THE BROWSER YOU ALREADY HAVE
• Read page text and find buttons, links and form fields.
• Fill inputs, choose options and click through browser tasks.
• Open, switch and organize tabs.
• Run custom page JavaScript supplied by your connected agent.
• Take screenshots so your agent can check the result.

CONNECT YOUR OWN AGENT
Built for Hermes Agent, with an MCP server for other MCP clients. MCP lets your agent call browser tools through a standard connection. Local Browser uses Chrome extension APIs and does not need a remote-debugging port.

YOU CONTROL THE CONNECTION
Pair the extension with your own relay. See its connection state and last task in the popup. Pause new browser commands whenever you want, reconnect, or forget the connection.

SETUP
This extension requires the free, open-source Local Browser Python relay and MCP setup on your agent's computer. Chrome and the agent can run on the same computer, or connect privately across computers with Tailscale and WSS. Import the pairing file from setup and click Connect my agent. Enable Allow User Scripts in Chrome's extension settings for custom JavaScript.

Start here: https://github.com/codejeet/local-browser

YOUR DATA
Requested page content and screenshots go to the relay and agent you choose, and may reach the agent's model provider or logs. Connect only to an agent you trust. Local Browser does not send browser content to a developer-run analytics or advertising service.

Privacy: https://github.com/codejeet/local-browser/blob/main/docs/privacy.md

## Dashboard fields

- Language: English
- Category: Productivity / Tools (choose the current matching dashboard label)
- Homepage: https://github.com/codejeet/local-browser
- Support: https://github.com/codejeet/local-browser/issues
- Privacy policy: https://github.com/codejeet/local-browser/blob/main/docs/privacy.md
- Single purpose: Connect a user's chosen AI agent to their existing Chrome profile for requested browser tasks: reading pages, interacting with forms and tabs, running page scripts, and capturing screenshots.

## Permission justifications

- `tabs`: Identify existing tabs by title and URL, select the intended tab for a requested task, and open, navigate, activate or close tabs. This is needed for agent-directed work across existing browser sessions.
- `scripting`: Run the bundled pageAction function for DOM snapshots, HTML reads, clicks, form fills, scroll and keyboard actions in the selected tab/frame. No downloaded JavaScript is passed to this API.
- `userScripts`: Run custom page scripts provided by the user's connected agent, including JavaScript expressions and async functions. The user enables Chrome's User Scripts toggle. Scripts execute in USER_SCRIPT or MAIN, separate from extension APIs; this preserves user-directed scripting rather than loading code into extension contexts.
- `storage`: Persist the user's relay URL, pairing credential, migration marker and pause setting locally. Access is restricted to trusted extension contexts; Chrome Sync is not used.
- `alarms`: Wake the service worker to reconnect to the user's configured relay after a disconnect. The alarm is inactive in effect while paused or unconfigured.
- `webNavigation`: List frame IDs and URLs for an explicitly requested frames action so the agent can target the intended iframe.
- `<all_urls>`: The core purpose is agent-directed work in arbitrary existing user tabs and frames, plus visible-tab screenshots, rather than a fixed site list or only a tab clicked in the toolbar. The user chooses the relay and agent, and can pause or remove the connection. Restricted Chrome pages remain inaccessible under Chrome's rules.

## Remote code answer

Yes: the eval action receives user/agent-provided page scripts via the authenticated user-selected relay and runs them only through `chrome.userScripts.execute`. All extension service-worker logic, popup logic and ordinary DOM actions are bundled. The scripting API receives only a bundled function. There are no remote script tags, remotely imported extension modules, eval/Function calls in extension contexts, or downloaded WebAssembly.

The MV3 policy expressly allows the User Scripts API exception when used for its documented purpose. The API documentation identifies arbitrary user-provided page scripts as that purpose. The requested eval capability is preserved and declared for review.

## Privacy practices

The extension handles browser information even when the user runs every component locally. Disclose website content, web history (requested tab URLs/titles), user activity (requested interactions), and authentication information (pairing token). Because requested page reads, scripts and screenshots can include private page content, also disclose personally identifiable information, personal communications, location, financial/payment information, and health information. These are possible contents of user-selected pages, not a separate analytics collection.

Certify the dashboard's limited-use declarations accurately: data is not sold to third parties; not used or transferred for purposes unrelated to the single purpose; and not used or transferred to determine creditworthiness or for lending. There is no developer-hosted data collection endpoint. The user's selected agent/provider can retain their own results, as disclosed in the popup and privacy policy.

## Artwork

- `store-icon.png`: 128 × 128 with transparent padding.
- `promo-small.png`: 440 × 280.
- `promo-marquee.png`: 1400 × 560.
- `screenshot-connected.png`: 1280 × 800, actual connected UI.
- `screenshot-setup.png`: 1280 × 800, actual fresh setup UI.
- `screenshot-workflow.png`: 1280 × 800, actual agent-filled demo page captured by the extension.
- `screenshot-paused.png`: 1280 × 800, actual paused UI.

## Official references checked

- https://developer.chrome.com/docs/webstore/program-policies/mv3-requirements
- https://developer.chrome.com/docs/extensions/reference/api/userScripts
- https://developer.chrome.com/docs/webstore/images
- https://developer.chrome.com/docs/webstore/program-policies/user-data-faq

The current image guide requires a 128px icon and at least one screenshot, recommends up to five screenshots at 1280 × 800, and supports 440 × 280 and 1400 × 560 promo art. The current User Scripts guide distinguishes Chrome 135–137 Developer mode from the Chrome 138+ per-extension Allow User Scripts toggle.
