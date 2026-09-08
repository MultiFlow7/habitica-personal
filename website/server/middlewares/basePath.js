import nconf from 'nconf';

// Strip the public prefix before upstream routes run. Root API routes remain
// available to the loopback health check and the existing SSH-tunnel CLI.
export default function basePath (req, res, next) {
  const prefix = nconf.get('APP_BASE_PATH') || '';
  if (!prefix) return next();
  if (!/^\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+$/.test(prefix)) {
    return next(new Error('Invalid APP_BASE_PATH'));
  }
  const redirect = res.redirect.bind(res);
  res.redirect = (...args) => {
    const index = args.length - 1;
    const target = args[index];
    if (typeof target === 'string' && target.startsWith('/') && !target.startsWith('//')
      && target !== prefix && !target.startsWith(`${prefix}/`) && !target.startsWith(`${prefix}?`)) {
      args[index] = prefix + target;
    }
    return redirect(...args);
  };
  if (req.path === prefix) return res.redirect(308, `${prefix}/${req.url.slice(prefix.length)}`);
  if (req.path.startsWith(`${prefix}/`)) {
    req.url = req.url.slice(prefix.length);
  } else if (req.method === 'GET' && !req.path.startsWith('/api/')) {
    return res.redirect(302, prefix + req.url);
  }
  return next();
}
