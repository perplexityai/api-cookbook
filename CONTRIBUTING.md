# Contributing to Perplexity API Cookbook

Thank you for your interest in contributing to our API Cookbook! We welcome high-quality examples that teach developers how to use the Perplexity API Platform.

## Structure

This cookbook contains two main sections:

### 1. **Examples** (`/docs/examples/`)
Step-by-step tutorials and example implementations that teach specific concepts or solve common use cases.

### 2. **Articles** (`/docs/articles/`)
In-depth integration guides and advanced implementation tutorials for complex use cases and integrations with other tools.

## Contributing Guidelines

### What We're Looking For

- **Clear, educational content** that helps developers understand how to use the Agent API, Search API, or Embeddings API effectively
- **Real-world use cases** that solve actual problems
- **Well-documented code** with clear explanations
- **Novel applications** that showcase unique ways to leverage the API

### Submission Format

All contributions should be in MDX format. If your project includes a full application (web app, CLI tool, etc.), host it in a separate public repository and link to it from your MDX file.

### MDX File Structure

Your MDX file should include:

```mdx
---
title: Your Project Title
description: A concise description of what your project does
sidebar_position: 1
keywords: [relevant, keywords, for, search]
---

# Project Title

Brief introduction explaining what your project does and why it's useful.

## Features

- Key feature 1
- Key feature 2
- Key feature 3

## Prerequisites

What users need before they can use your project.

## Installation

Step-by-step installation instructions.

## Usage

Clear examples of how to use your project.

## Code Explanation

Key code snippets with explanations of how they work.

## Links

- [GitHub Repository](https://github.com/yourusername/yourproject)
- [Live Demo](https://yourproject.com) (if applicable)

## Limitations

Any known limitations or considerations users should be aware of.
```

## How to Submit

### For Examples

1. Fork this repository
2. Create a new directory under `/docs/examples/your-example-name/`
3. Add your `README.mdx` file following the structure above
4. Include any necessary code snippets in your MDX file
5. Submit a pull request

### For Articles

1. Fork this repository
2. Create a new directory under `/docs/articles/your-article-name/`
3. Add your `README.mdx` file following the structure above
4. Focus on advanced implementations, integrations, or complex patterns
5. Include comprehensive code examples and explanations
6. Submit a pull request

## Pull Request Template

When submitting a PR, please use this template:

```markdown
## Description
Brief description of your contribution

## Type of Contribution
- [ ] Example Tutorial
- [ ] Article/Integration Guide

## Checklist
- [ ] My code follows the cookbook's style guidelines
- [ ] I have included comprehensive documentation
- [ ] I have tested my code and it works as expected
- [ ] I have included all necessary dependencies and setup instructions
- [ ] My MDX file includes proper frontmatter (title, description, keywords)
- [ ] I have linked to any external repositories or live demos

## Project Details
**What problem does this solve?**

**What makes this contribution valuable to other developers?**

**External Links (if applicable):**
- GitHub Repository: 
- Live Demo: 
- Blog Post/Article: 
```

## Code Quality Standards

- Use clear, descriptive variable and function names
- Include comments for complex logic
- Follow the language's standard conventions
- Handle errors appropriately
- Include example environment variables (without actual keys)

## What to Avoid

- Basic "Hello World" examples that don't demonstrate real use cases
- Duplicates of existing cookbook examples
- Projects with security vulnerabilities
- Poorly documented code

## Need Help?

If you have questions about contributing, please:
1. Check existing examples for reference
2. Open an issue for discussion before starting major work
3. Contact us at api@perplexity.ai for specific questions

We look forward to seeing your creative applications of the Perplexity API Platform!
