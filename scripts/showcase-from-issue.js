#!/usr/bin/env node
// Turns a "Submit a showcase project" issue (GitHub issue form) into
// docs/showcase/<slug>.mdx. Free-text fields are treated as plain Markdown:
// HTML tags, JSX braces, import/export lines, and code blocks are removed.
// The result still goes through scripts/validate-showcase.js before a PR opens.
//
// Usage: ISSUE_BODY="$(gh issue view N --json body -q .body)" node scripts/showcase-from-issue.js
// Prints the path of the file it wrote.

import fs from 'fs';
import path from 'path';

const body = process.env.ISSUE_BODY || '';
if (!body.trim()) { console.error('ISSUE_BODY is empty'); process.exit(1); }

// Issue forms render each field as "### <label>\n\n<value>\n\n".
function parseIssueForm(text) {
  const fields = {};
  const parts = text.split(/^### /m).slice(1);
  for (const part of parts) {
    const nl = part.indexOf('\n');
    const label = part.slice(0, nl).trim();
    let value = part.slice(nl + 1).trim();
    if (value === '_No response_') value = '';
    fields[label] = value;
  }
  return fields;
}

function sanitizeText(s) {
  return s
    .replace(/```[\s\S]*?```/g, '')           // fenced code
    .replace(/^\s*(import|export)\s.*$/gm, '') // module lines
    .replace(/<[^>]*>/g, '')                   // any tag
    .replace(/[{}]/g, '')                      // JSX expressions
    .replace(/javascript:/gi, '')
    .replace(/\]\(http:\/\//g, '](https://')   // upgrade plain http links
    .replace(/[<>]/g, (c) => (c === '<' ? '&lt;' : '&gt;'))
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function sanitizeLine(s) {
  return sanitizeText(s).replace(/\s+/g, ' ').replace(/["\n]/g, '').trim();
}

function list(s) {
  return s.split(',').map((x) => x.trim().toLowerCase()).filter(Boolean);
}

function httpsUrl(s) {
  const v = s.trim();
  return /^https:\/\/[^\s"'<>]+$/.test(v) ? v : '';
}

const f = parseIssueForm(body);
const name = sanitizeLine(f['Project name'] || '');
const slug = (f['URL slug'] || '').trim().toLowerCase();
const description = sanitizeLine(f['One-sentence description'] || '');
const repo = httpsUrl(f['Public repository URL'] || '');
const demo = httpsUrl(f['Live demo URL (optional)'] || '');
const products = list(f['Which Perplexity APIs does it use?'] || '');
const categories = list(f['Categories (pick up to 3)'] || '').slice(0, 3);
const keywords = list(f['Keywords'] || '').slice(0, 8);
const screenshot = httpsUrl(f['Screenshot URL (optional)'] || '');
const video = (f['YouTube video URL (optional)'] || '').trim();
const about = sanitizeText(f['What does it do?'] || '');
const apiUsage = sanitizeText(f['How does it use the Perplexity API?'] || '');
const author = sanitizeLine(f['Built by (optional)'] || '');

const problems = [];
if (!name) problems.push('Project name is empty');
if (!/^[a-z0-9][a-z0-9-]*$/.test(slug)) problems.push(`URL slug "${slug}" must be lowercase letters, digits, and hyphens`);
if (!description) problems.push('Description is empty');
if (!repo) problems.push('Repository URL must be an https URL');
if (products.length === 0) problems.push('At least one product is required');
if (problems.length) { console.error(problems.join('\n')); process.exit(1); }

let videoId = '';
const vm = video.match(/(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{6,})/);
if (vm) videoId = vm[1];

const fm = [
  '---',
  `title: ${name}`,
  `description: ${description}`,
  `keywords: [${keywords.join(', ')}]`,
  `products: [${products.join(', ')}]`,
  `categories: [${categories.join(', ')}]`,
  '---',
].join('\n');

const sections = [];
if (screenshot) sections.push(`![Screenshot of ${name}](${screenshot})`);
sections.push(about);
if (videoId) {
  sections.push(`<iframe src="https://www.youtube.com/embed/${videoId}" title="${name} demo" allowfullscreen></iframe>`);
}
sections.push(`## How it uses the Perplexity API\n\n${apiUsage}`);
const links = [`- [Repository](${repo})`];
if (demo) links.push(`- [Live demo](${demo})`);
sections.push(`## Try it\n\n${links.join('\n')}`);
if (author) sections.push(`## Built by\n\n${author}`);

const out = `${fm}\n\n${sections.filter(Boolean).join('\n\n')}\n`;
const file = path.join('docs', 'showcase', `${slug}.mdx`);
fs.mkdirSync(path.dirname(file), { recursive: true });
fs.writeFileSync(file, out);
console.log(file);
