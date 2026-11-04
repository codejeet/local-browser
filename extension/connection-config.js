// Shared by the classic service worker. No credentials ship with the extension.
const ConnectionConfig = Object.freeze({
  validateUrl(value) {
    const invalid = () => Error('Relay URL must use wss:// for remote hosts or ws:// for loopback, end in /extension, and contain no credentials, query or fragment');
    if (typeof value !== 'string' || /[\s\x00-\x1f\\?#]/.test(value)) throw invalid();
    let url;
    try { url = new URL(value); } catch { throw invalid(); }
    const authority = value.match(/^wss?:\/\/([^/]+)/i)?.[1];
    if (!authority || authority.includes('@') || !['ws:', 'wss:'].includes(url.protocol) ||
        !url.hostname || url.username || url.password || !url.pathname.endsWith('/extension') ||
        (url.port && Number(url.port) < 1)) throw invalid();
    const host = url.hostname.toLowerCase();
    const loopback = host === 'localhost' || host === 'localhost.' || host === '[::1]' ||
      /^127(?:\.\d{1,3}){3}$/.test(host);
    if (url.protocol === 'ws:' && !loopback) throw invalid();
    return value;
  },
  parse(value, previous = null) {
    const url = this.validateUrl(value?.url);
    if (value?.token != null && typeof value.token !== 'string') throw Error('Pairing token must be text');
    const token = value?.token?.trim() || previous?.token;
    if (!token) throw Error('Enter the pairing token from your relay setup');
    return {url, token};
  }
});
