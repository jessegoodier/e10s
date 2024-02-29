# OAuth2 Proxy Helm Installation

```sh
helm upgrade --install oauth2-proxy-e10s \
  --repo https://oauth2-proxy.github.io/manifests oauth2-proxy \
  -f oauth.yaml
```
