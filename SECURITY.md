# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | ✅ Active development |

## Reporting a Vulnerability

Vulnerabilities can be reported by:
- Opening a [GitHub Issue](https://github.com/anomalyco/vyapaar-bandhu/issues)
- Emailing the maintainers directly

You should expect an acknowledgement within 48 hours and a remediation timeline within 7 days.

## Security Posture

### Current Measures
- **JWT Authentication**: Bearer token with HS256 signing (configurable via `JWT_SECRET`)
- **Password Hashing**: bcrypt with salt
- **Rate Limiting**: slowapi with per-endpoint limits (60/min default, 10/min on auth)
- **Input Validation**: Pydantic models + HTML sanitization on user text inputs
- **File Validation**: MIME type + size restrictions on uploads
- **Security Headers**: X-Content-Type-Options, X-Frame-Options, XSS-Protection, HSTS, Cache-Control
- **CORS**: Configurable via `CORS_ORIGINS` env var (defaults to `*` for development)
- **SQL Injection**: Prevented by SQLAlchemy ORM (parameterized queries)

### Known Gaps
1. **Authentication on data routes**: ~90% of API endpoints (dashboard, clients, invoices, OCR) are currently unauthenticated. Add `get_current_ca` dependency to sensitive routes before production deployment.
2. **Keys in git history**: Live API keys were committed in commits `6146fa3` and `6020f4b`. All credentials **must be rotated** before production.
3. **JWT token lifetime**: 30-day expiry with no refresh mechanism. Reduce in production.
4. **JWT storage**: Frontend stores token in `localStorage` (XSS-vulnerable). Migrate to `httpOnly` cookies.
5. **No HTTPS enforcement**: Add HTTPS redirect middleware in production.
6. **No CSRF protection**: Add for state-changing endpoints in production.
7. **No dependency vulnerability scanning**: Run `pip-audit` or `safety` check regularly.

### Recommended Production Configuration

```bash
# Required
JWT_SECRET=<random 64-char hex string>
DATABASE_URL=<production database URL with SSL>

# Security
CORS_ORIGINS=https://your-frontend-domain.com
JWT_EXPIRE_DAYS=1
RATE_LIMIT_DEFAULT=100/hour

# Harden
# - Enable HTTPS at reverse proxy level
# - Use httpOnly cookies for JWT storage
# - Add webhook signature verification for Twilio
# - Implement audit logging
```
