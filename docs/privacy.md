# Local Browser privacy policy

Local Browser connects the Chrome profile you choose to an AI agent through a relay you set up. This policy covers the Chrome extension and the relay/MCP tools in this repository.

## What the extension handles

- Your relay address, pairing token and pause setting are saved locally in your Chrome profile. They are not synced through Chrome Sync. The pairing token is kept out of ordinary web-page access.
- When your connected agent requests it, the extension can return open-tab titles and URLs, page text, HTML, form values, frame information, JavaScript results and screenshots. Depending on the page, this can include names, contact details, messages, account information, financial or health information, and other private content.
- The agent can click, type, navigate and run page scripts using your existing signed-in session. The extension does not need your account passwords to reuse that session. Requested page content or scripts may still encounter sensitive information on the page.
- Connection state and the last action's name, time and success state are held in memory for the popup. The extension does not continuously record your browsing history.

## Where information goes

Requested page content and screenshots travel to your chosen relay and agent. The agent may send them to its model provider and retain them in conversation history or logs. Those tools' settings and policies govern their processing and retention. Use an agent and relay you trust.

The extension has no developer-operated collection endpoint, analytics service or advertising service. The project does not sell browser data or use it for ads. Data access is used to carry out your browser automation tasks.

Remote relay connections require encrypted WSS. Same-computer connections may use loopback WebSockets. The relay uses separate extension and operator credentials and checks the extension's origin. The pairing credential is stored in Chrome local extension storage; your device and Chrome profile protect that storage.

## Storage and deletion

The extension keeps its connection settings until you choose **Connection settings → Forget connection** or uninstall it. Forgetting the connection removes the stored relay address and token. **Pause** stops new commands; a command already running may finish.

The relay keeps pending commands and connection state in memory and does not log command bodies or page results. The CLI prints requested results to your terminal. The MCP tool saves screenshots in its private local cache until you remove them. The agent and any model provider may keep their own copies; manage those in the tools you chose.

Relay setup also creates private `config.json` and `pairing.json` files. Legacy unpacked setups may include `extension/connection.js`. Delete these files when you retire the connection. Uninstalling the extension does not remove files from your agent's computer.

## Limited use

Local Browser's use and transfer of information received from Google APIs follows the [Chrome Web Store User Data Policy](https://developer.chrome.com/docs/webstore/program-policies/user-data), including its Limited Use requirements. Browser information is used for the extension's stated browser automation purpose, not advertising, profiling or unrelated data collection.

## Questions

Contact the maintainer through [GitHub issues](https://github.com/codejeet/local-browser/issues). Describe the issue without posting tokens or private page content.
