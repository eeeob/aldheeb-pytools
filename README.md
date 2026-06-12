# aldheeb-pytools 🛠️

[![PyPI version](https://img.shields.io/pypi/v/aldheeb-pytools)](https://pypi.org/project/aldheeb-pytools/)
[![Python versions](https://img.shields.io/pypi/pyversions/aldheeb-pytools)](https://pypi.org/project/aldheeb-pytools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**aldheeb-pytools** is a modern Python utilities library providing async-ready helpers for backend systems, databases, cryptography, and Telegram automation.

---

## ✨ Features

* ⚡ **Async-first design** built for modern `asyncio` applications
* 🗄️ **MongoDB utilities** for cleaner and safer database operations
* 🔐 **Cryptography helpers** (AES-GCM, secure key derivation)
* 🤖 **Telegram utilities** using Kurigram integration
* 📧 **IMAP email utilities** for fetching and parsing emails
* 🌍 **Country & phone utilities** for region and number handling
* 🧰 **General utilities** for parsing, validation, and data handling
* 🧩 **Fully typed codebase** with strict type hints support

---

## 📦 Installation

Starting from `v0.2.0`, the library uses **optional dependencies** — install only what you need.

### Minimal install (no optional dependencies)

```bash
pip install aldheeb-pytools
```

### Install specific features

| Extra | Installs | Use for |
|-------|----------|---------|
| `crypto` | `cryptography` | Encryption & key derivation |
| `mongo` | `pymongo` | MongoDB utilities |
| `phone` | `phonenumbers` | Phone number parsing |
| `country` | `pycountry`, `phonenumbers` | Country info & region codes |
| `tg` | `kurigram` | Telegram automation |
| `aiologic` | `aiologic` | aio automation
| `imap` | `aioimaplib` | IMAP email fetching |
| `bs4` | `beautifulsoup4` | HTML email parsing |
| `full` | everything above | All features |

```bash
# Single feature
pip install "aldheeb-pytools[crypto]"

# Multiple features
pip install "aldheeb-pytools[crypto, mongo, phone]"

# Everything
pip install "aldheeb-pytools[full]"
```

> **Note:** If you try to use a feature without its required packages installed, you'll get a clear `ImportError` with the exact install command needed.

---

## 🚀 Quick Start

### 🔐 Encryption example

```bash
pip install "aldheeb-pytools[crypto]"
```

```python
from pytools import encrypt, decrypt

key = "my-secure-key"

encrypted = encrypt("secret data", key)
print(encrypted)

decrypted = decrypt(encrypted, key)
print(decrypted)
```

### 🗄️ MongoDB example

```bash
pip install "aldheeb-pytools[mongo]"
```

```python
from pytools import MongoIndex

index = MongoIndex.from_dict({"key": {"field": 1}})
```

### 🤖 Telegram example

```bash
pip install "aldheeb-pytools[tg]"
```

```python
from pytools import format_tg_username, mention_tg_user

username = format_tg_username("@myuser")
mention = mention_tg_user(123456789, "John")
```

---

## 🧪 Development Setup

```bash
git clone https://github.com/eeeob/aldheeb-pytools.git
cd aldheeb-pytools
pip install -e ".[dev]"
```

---

## 📄 License

This project is licensed under the **MIT License**.
See the [LICENSE](LICENSE) file for details.

---

## 📬 Contact

* Email: [aldheeb01@gmail.com](mailto:aldheeb01@gmail.com)
* GitHub: https://github.com/eeeob/aldheeb-pytools
