# Changelog

All notable user-facing changes to `aynse` are recorded here.

## 2.3.1 - 2026-08-10

### Fixed

- Restored documented historical record keys while retaining the 2.3.0 keys
  as compatibility aliases.
- Corrected NSE derivative expiry calculations across the 2024 weekly-contract
  retirements and the September 2025 Tuesday-expiry transition. Futures no
  longer receive fictional weekly expiries.
- Added the official 2026 Capital Market trading calendar, including the
  January 15 exchange amendment, so trading-day and expiry adjustment helpers
  do not treat holidays as sessions.
- Made the historical bhavcopy fallback skip known exchange holidays instead
  of issuing guaranteed-empty archive requests.
- Made `NSELive.get_options_around_date()` honor its inclusive `days_after`
  argument and reject invalid window values.
- Deferred async lock construction so the advertised Python 3.9 runtime can
  construct async clients without a running event loop.

### Security

- Removed an unused tracked cookie pickle and ignored that local artifact so
  session material cannot be recommitted accidentally.

### Compatibility

- Stock records now expose canonical `last_traded_price` plus legacy
  `last_price`.
- Derivative records now expose canonical `expiry_date`, `last_traded_price`,
  `settlement_price`, and `lot_size` plus their legacy aliases.
- No existing top-level import was removed.
