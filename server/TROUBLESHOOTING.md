# PipeCat Bot Troubleshooting Guide

This guide addresses common issues when running the PipeCat bot on macOS.

## Common Issues and Solutions

### 1. SSL Certificate Verification Failed

**Error Message:**
```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

**Solution:**
The SSL certificate issue is common on macOS. We've implemented several fixes:

1. **Updated SSL certificates** using the macOS certificate installer
2. **Added SSL environment variables** in the bot code
3. **Installed additional SSL packages** (certifi, pyOpenSSL, requests)

**Manual Fix (if needed):**
```bash
# Run the macOS certificate installer
/Applications/Python\ 3.12/Install\ Certificates.command

# Or manually set environment variables
export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")
export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE
```

### 2. NLTK Resource Missing

**Error Message:**
```
Resource punkt_tab not found.
Please use the NLTK Downloader to obtain the resource
```

**Solution:**
We've downloaded the required NLTK resources:

1. **punkt** - for sentence tokenization
2. **punkt_tab** - for tabular tokenization
3. **averaged_perceptron_tagger** - for part-of-speech tagging

**Manual Fix (if needed):**
```bash
# Activate virtual environment
source ../.venv/bin/activate

# Download required NLTK resources
python -c "import nltk; nltk.download('punkt')"
python -c "import nltk; nltk.download('punkt_tab')"
python -c "import nltk; nltk.download('averaged_perceptron_tagger')"
```

### 3. Running the Bot

**Option 1: Use the startup script (recommended)**
```bash
cd server
./start_bot.sh
```

**Option 2: Run directly with Python**
```bash
cd server
source ../.venv/bin/activate
python bot.py
```

**Option 3: Use the modified bot with built-in fixes**
```bash
cd server
source ../.venv/bin/activate
python bot.py  # The bot.py now includes SSL and NLTK fixes
```

## Verification

Run the test script to verify everything is working:
```bash
cd server
source ../.venv/bin/activate
python test_ssl.py
```

You should see:
```
🎉 All tests passed! Your setup should work now.
```

## Environment Variables

The following environment variables are automatically set:

- `SSL_CERT_FILE` - Path to SSL certificate bundle
- `REQUESTS_CA_BUNDLE` - Path to requests CA bundle
- `NLTK_DATA` - Path to NLTK data directory

## Dependencies

Additional packages installed to fix the issues:
- `certifi>=2025.8.3` - SSL certificates
- `urllib3>=2.0.0` - HTTP client
- `requests>=2.31.0` - HTTP library
- `pyOpenSSL>=23.0.0` - SSL/TLS toolkit
- `nltk>=3.9.0` - Natural language processing

## Notes

- The bot now includes built-in SSL and NLTK fixes
- SSL certificates are automatically configured
- NLTK resources are downloaded to `~/nltk_data`
- All fixes are backward compatible
