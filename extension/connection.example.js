// Template only. Run setup.py to create the ignored connection.js with a fresh token.
// Use wss://relay.example.com/extension for a remote relay behind HTTPS.
// Never put the operator token in the extension or commit real credentials.
const CONNECTION = Object.freeze({
  url: 'ws://127.0.0.1:18210/extension',
  token: 'REPLACE_WITH_GENERATED_EXTENSION_TOKEN'
});
