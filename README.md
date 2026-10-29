# KenyaESG guide

A private RU/EN guide to ESG, carbon accounting and climate compliance in Kenya, published with GitHub Pages from `docs/`.

The page text is encrypted (PBKDF2-SHA256, 600,000 iterations → AES-256-GCM) and decrypted in the browser after sign-in. The Markdown sources are **not** stored in this public repository; only the encrypted payloads are.

## Rebuild or change the password

```bash
pip install markdown cryptography
SITE_USER=kenyaesg SITE_PASSWORD='new-password' python3 tools/build.py path/to/guide_ru.md path/to/guide_en.md
git add docs && git commit -m "Rebuild guide" && git push
```

Every build uses a new salt, so a rebuild with a new password locks out the old one. People who ticked "Remember on this device" are signed out on their next visit because the old key no longer decrypts the text.

## Limits

GitHub Pages has no server-side login. Anyone can download the encrypted files, so the protection is only as strong as the password: use a long random one and change it if it leaks.
