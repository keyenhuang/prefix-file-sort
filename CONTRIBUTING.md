# Contributing to prefix-file-sort

Thank you for your interest in contributing to prefix-file-sort! This document provides guidelines and instructions for contributing.

## 🤝 How to Contribute

### Reporting Bugs

Before submitting a bug report:
1. Search existing issues to avoid duplicates
2. Update to the latest version to verify the issue persists
3. Include detailed information:
   - Python version
   - Operating system
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages or logs

### Suggesting Features

We welcome feature suggestions! Please:
1. Check existing issues and discussions first
2. Describe the use case and motivation
3. Explain how the feature should work
4. Provide code examples if applicable

### Pull Requests

1. **Fork the Repository**
   ```bash
   git clone https://github.com/keyenhuang/prefix-file-sort.git
   cd prefix-file-sort
   ```

2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Set Up Development Environment**
   ```bash
   pip install tkinterdnd2
   python main.py
   ```

4. **Make Your Changes**
   - Follow the code style guidelines below
   - Add comments for complex logic
   - Test your changes thoroughly

5. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "Add: brief description of changes"
   ```

6. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

## 📋 Code Style Guidelines

### Python Code

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use meaningful variable and function names
- Add type hints where applicable
- Keep functions focused and small

### Example

```python
# Good
def preview_groups(self, filter_text: str, suffix: str, use_numbering: bool) -> Dict[str, List[Path]]:
    """Preview how files will be grouped before execution."""
    files = self.get_filtered_files(filter_text)
    # ...

# Avoid
def pg(f, s, n):
    files = self.get_filtered_files(f)
    # ...
```

### Documentation

- Add docstrings to all public methods and classes
- Update README.md if adding new features
- Add inline comments for complex logic

## ✅ Checklist Before Submitting

- [ ] Code follows the style guidelines
- [ ] New code includes appropriate docstrings
- [ ] README.md is updated (if applicable)
- [ ] No unnecessary files are committed
- [ ] Changes are tested manually

## 📝 Commit Message Format

Use conventional commits:

```
<type>: <subject>

<body>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests

Example:
```
feat: Add numbered custom mode for folder naming

Allow users to specify custom folder names when using numbered mode.
Files with numeric prefixes will use the corresponding custom name.
```

## 🔄 Pull Request Process

1. Fill out the PR template completely
2. Link any related issues
3. Ensure CI/CD checks pass
4. Request review from maintainers
5. Address feedback and push updates

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Thank You

Every contribution, no matter how small, helps make this project better for everyone. Thank you for taking the time to contribute!
