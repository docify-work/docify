// CloudFront Function (runtime cloudfront-js-2.0), event: viewer-request.
// Attached to the DEFAULT behaviour ("/*" -> S3 web bucket) only, never to
// "/api/*" (API 404s must stay real 404s - that's also why the distribution
// has no custom error responses). Master Doc §12.5.
//
// 1) www.<domain> -> 301 https://<domain><same path + query>
//    Only the prod distribution has a www alias, so on staging this branch
//    never runs. Keeping it here (instead of a 2nd function) keeps one function
//    per behaviour, which is all a viewer-request slot allows.
// 2) SPA rewrite: React Router owns client-side routes like /w/acme/docs/42.
//    S3 has no such object, so any path whose last segment has no file
//    extension is served /index.html. Real files (/assets/app.3f2a.js,
//    /config.json, /favicon.ico) pass through untouched.

function handler(event) {
  var request = event.request;
  var host = request.headers.host ? request.headers.host.value : '';

  if (host.indexOf('www.') === 0) {
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        location: { value: 'https://' + host.substring(4) + request.uri + buildQuery(request.querystring) },
        'cache-control': { value: 'max-age=3600' }
      }
    };
  }

  var uri = request.uri;
  var lastSegment = uri.substring(uri.lastIndexOf('/') + 1);
  if (lastSegment.indexOf('.') === -1) {
    request.uri = '/index.html';
  }
  return request;
}

// Rebuild "?a=1&b=2" from CloudFront's querystring object (values arrive
// already URL-encoded, so they are copied as-is).
function buildQuery(querystring) {
  var parts = [];
  for (var key in querystring) {
    var param = querystring[key];
    if (param.multiValue) {
      for (var i = 0; i < param.multiValue.length; i++) {
        parts.push(pair(key, param.multiValue[i].value));
      }
    } else {
      parts.push(pair(key, param.value));
    }
  }
  return parts.length > 0 ? '?' + parts.join('&') : '';
}

function pair(key, value) {
  return value === '' ? key : key + '=' + value;
}
