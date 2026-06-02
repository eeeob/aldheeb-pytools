# aldheeb-pytools 🛠️

[![PyPI version](https://img.shields.io/pypi/v/aldheeb-pytools.svg)](https://pypi.org/project/aldheeb-pytools/)
[![Python versions](https://img.shields.io/pypi/pyversions/aldheeb-pytools.svg)](https://pypi.org/project/aldheeb-pytools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**aldheeb-pytools** is a modern Python utilities library providing async-ready helpers for backend systems, databases, cryptography, and Telegram automation.

---

## ✨ Features

* ⚡ **Async-first design** built for modern `asyncio` applications
* 🗄️ **MongoDB utilities** for cleaner and safer database operations
* 🔐 **Cryptography helpers** (AES-GCM, secure key derivation)
* 🤖 **Telegram utilities** using Kurigram integration
* 🧰 **General utilities** for parsing, validation, and data handling
* 🧩 **Fully typed codebase** with strict type hints support

---

## 📦 Installation

### Basic install

```bash
pip install aldheeb-pytools
```

### With optional dependencies

```bash
pip install "aldheeb-pytools[full]"
```

---

## 🚀 Quick Start

### 🔐 Encryption example

```python
from pytools import encrypt, decrypt

key = "my-secure-key"

encrypted = encrypt("secret data", key)
print(encrypted)

decrypted = decrypt(encrypted, key)
print(decrypted)
```

---

## 🧪 Development Setup

```bash
git clone https://github.com/eeeob/aldheeb-pytools.git
cd aldheeb-pytools
pip install -e .[dev]
```

---

## 📄 License

This project is licensed under the **MIT License**.
See the [LICENSE](LICENSE) file for details.

---

## 📬 Contact

* Email: [aldheeb01@gmail.com](mailto:aldheeb01@gmail.com)
* GitHub: https://github.com/eeeob/aldheeb-pytools

---
