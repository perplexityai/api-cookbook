#!/usr/bin/env node
// Validates community showcase pages under docs/showcase/.
//
// Showcase files come from outside contributors and are copied into the docs
// build, so this is a content gate, not just an MDX compile check:
//   - flat frontmatter with a fixed schema
//   - products limited to current APIs (Sonar is rejected)
//   - no imports, exports, scripts, styles, or event handlers
//   - only an allowlisted set of tags; iframes only from YouTube
//   - images over https or committed under static/showcase/<slug>/
//
// Usage: node scripts/validate-showcase.js [files...]
// With no arguments it validates every docs/showcase/*.mdx.

import fs from 'fs';
import path from 'path';
import { glob } from 'glob';

const ALLOWED_PRODUCTS = ['agent-api', 'search-api', 'embeddings-api'];
const ALLOWED_CATEGORIES = [
  'finance', 'people', 'sandbox', 'multimodal', 'rag', 'deep-research',
  'structured-outputs', 'function-calling', 'streaming', 'memory',
  'search-filtering', 'orchestration', 'integrations', 'mcp',
];
const ALLOWED_TAGS = new Set(['img', 'iframe', 'br', 'Note', 'Tip', 'Warning', 'Info', 'Frame']);
const YOUTUBE_EMBED = /^https:\/\/www\.youtube(-nocookie)?\.com\/embed\/[A-Za-z0-9_-]+(\?[A-Za-z0-9_=&-]*)?$/;
const SLUG = /^[a-z0-9][a-z0-9-]*$/;

function parseFrontmatter(src, errors) {
  const m = src.match(/^---\n([\s\S]*?)\n---\n/);
  if (!m) { errors.push('missing frontmatter block'); return { fm: {}, body: src }; }
  const fm = {};
  for (const raw of m[1].split('\n')) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    if (/^\s/.test(line)) { errors.push(`frontmatter must be flat; unexpected indented line: "${line.trim()}"`); continue; }
    const kv = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (!kv) { errors.push(`frontmatter line is not key: value: "${line}"`); continue; }
    const [, key, valueRaw] = kv;
    let value = valueRaw.trim();
    if (value.startsWith('[') && value.endsWith(']')) {
      value = value.slice(1, -1).split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
    } else {
      value = value.replace(/^['"]|['"]$/g, '');
    }
    fm[key] = value;
  }
  return { fm, body: src.slice(m[0].length) };
}

function stripCode(body) {
  return body.replace(/```[\s\S]*?```/g, '').replace(/`[^`\n]*`/g, '');
}

function validateFile(file) {
  const errors = [];
  const slug = path.basename(file, '.mdx');
  if (!SLUG.test(slug)) errors.push(`filename must be lowercase letters, digits, and hyphens: ${slug}.mdx`);

  const src = fs.readFileSync(file, 'utf8');
  const { fm, body } = parseFrontmatter(src, errors);

  const allowedKeys = new Set(['title', 'description', 'keywords', 'products', 'categories']);
  for (const k of Object.keys(fm)) if (!allowedKeys.has(k)) errors.push(`unknown frontmatter key: ${k}`);

  if (typeof fm.title !== 'string' || !fm.title) errors.push('title is required');
  else if (fm.title.length > 60) errors.push(`title is ${fm.title.length} chars; keep it under 60`);

  if (typeof fm.description !== 'string' || !fm.description) errors.push('description is required');
  else if (fm.description.length > 160) errors.push(`description is ${fm.description.length} chars; keep it under 160`);

  if (!Array.isArray(fm.keywords) || fm.keywords.length < 3 || fm.keywords.length > 8) {
    errors.push('keywords must be a list of 3 to 8 items');
  }

  if (!Array.isArray(fm.products) || fm.products.length === 0) {
    errors.push(`products is required; allowed: ${ALLOWED_PRODUCTS.join(', ')}`);
  } else {
    for (const p of fm.products) {
      if (p === 'sonar-api') errors.push('sonar-api is not accepted; Sonar is deprecated. Use agent-api, search-api, or embeddings-api');
      else if (!ALLOWED_PRODUCTS.includes(p)) errors.push(`unknown product "${p}"; allowed: ${ALLOWED_PRODUCTS.join(', ')}`);
    }
  }

  if (fm.categories !== undefined) {
    if (!Array.isArray(fm.categories)) errors.push('categories must be a list');
    else for (const c of fm.categories) if (!ALLOWED_CATEGORIES.includes(c)) errors.push(`unknown category "${c}"; allowed: ${ALLOWED_CATEGORIES.join(', ')}`);
  }

  const text = stripCode(body);

  if (/^\s*(import|export)\s/m.test(text)) errors.push('import/export statements are not allowed');
  if (/<\s*(script|style|object|embed|form|input|link|meta|base)\b/i.test(text)) errors.push('script, style, object, embed, form, and similar tags are not allowed');
  if (/\son[a-z]+\s*=/i.test(text)) errors.push('inline event handlers (onClick, onLoad, ...) are not allowed');
  if (/javascript:/i.test(text)) errors.push('javascript: URLs are not allowed');
  if (/\{[^}\n]*\}/.test(text.replace(/!\[[^\]]*\]\([^)]*\)/g, ''))) errors.push('JSX expressions in braces are not allowed');
  if (/http:\/\//.test(text)) errors.push('http:// URLs are not allowed; use https');

  for (const tag of text.matchAll(/<\s*\/?\s*([A-Za-z][\w.-]*)/g)) {
    if (!ALLOWED_TAGS.has(tag[1])) errors.push(`tag <${tag[1]}> is not allowed; allowed: ${[...ALLOWED_TAGS].join(', ')}`);
  }

  for (const iframe of text.matchAll(/<iframe\b[^>]*>/gi)) {
    const src = iframe[0].match(/\bsrc\s*=\s*["']([^"']+)["']/i);
    if (!src || !YOUTUBE_EMBED.test(src[1])) errors.push(`iframe src must be a YouTube embed URL: ${src ? src[1] : '(missing src)'}`);
  }

  const imageUrls = [];
  for (const md of text.matchAll(/!\[[^\]]*\]\(([^)\s]+)[^)]*\)/g)) imageUrls.push(md[1]);
  for (const img of text.matchAll(/<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']/gi)) imageUrls.push(img[1]);
  for (const url of imageUrls) {
    if (url.startsWith('https://')) continue;
    const localPrefix = `/static/showcase/${slug}/`;
    if (url.startsWith(localPrefix)) {
      const onDisk = path.join('static', 'showcase', slug, url.slice(localPrefix.length));
      if (!fs.existsSync(onDisk)) errors.push(`image not found in repo: ${url}`);
      continue;
    }
    errors.push(`image must be an https URL or live under ${localPrefix}: ${url}`);
  }

  if (text.trim().length < 300) errors.push('body is too short; describe the project and how it uses the Perplexity API');

  return [...new Set(errors)];
}

async function main() {
  const args = process.argv.slice(2);
  const files = args.length ? args : await glob('docs/showcase/*.mdx');
  if (files.length === 0) { console.log('No showcase files to validate.'); return; }

  let failed = 0;
  for (const file of files.sort()) {
    const errors = validateFile(file);
    if (errors.length) {
      failed += 1;
      console.error(`\n❌ ${file}`);
      for (const e of errors) console.error(`   - ${e}`);
    } else {
      console.log(`✅ ${file}`);
    }
  }
  if (failed) {
    console.error(`\n${failed} of ${files.length} showcase file(s) failed validation. See CONTRIBUTING.md for the template.`);
    process.exit(1);
  }
  console.log(`\n🎉 ${files.length} showcase file(s) valid.`);
}

main();
