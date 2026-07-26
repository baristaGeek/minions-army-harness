# Logs Directory

Application log files are written here during local execution.

## Files

- `minions-army.log`: main application log file.

## Configuration

Logging is configured in `src/infrastructure/logging.py`.

The default log level depends on the `ENVIRONMENT` setting:

- `production`: `INFO`
- any other value: `DEBUG`

## Guidance

- Do not commit generated log files.
- Avoid logging secrets, tokens, credentials, or full external payloads that may contain sensitive data.
- Use logs to capture actionable operational context, especially around webhook handling and Docker minion startup.
