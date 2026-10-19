import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const scripts = path.dirname(fileURLToPath(import.meta.url));

test('generated pages accept supported products and reject executable MDX', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'showcase-products-'));
  try {
    const issue = [
      ['Project name', 'Decision helper'],
      ['URL slug', 'decision-helper'],
      ['One-sentence description', 'Compare a fixed set of choices.'],
      ['Public repository URL', 'https://example.com/decision-helper'],
      ['Which Perplexity APIs does it use?', 'decisions-api'],
      ['Categories (pick up to 3)', 'integrations'],
      ['Keywords', 'decisions, choices, comparison'],
      ['What does it do?', 'This project helps a reader compare a fixed set of choices and inspect the resulting recommendation. It presents the alternatives with enough context to understand the outcome and keeps the original question visible beside the result.'],
      ['How does it use the Perplexity API?', 'The project sends its alternatives to the Decisions API and displays the returned decision. It handles unsuccessful requests and lets the reader review the recommendation before acting on it.'],
    ].map(([label, value]) => `### ${label}\n\n${value}`).join('\n\n');
    const generated = spawnSync(process.execPath, [path.join(scripts, 'showcase-from-issue.js')], {
      cwd: directory, env: { ...process.env, ISSUE_BODY: issue }, encoding: 'utf8',
    });
    assert.equal(generated.status, 0, generated.stderr);
    const file = path.join(directory, generated.stdout.trim());
    const validate = () => spawnSync(process.execPath, [path.join(scripts, 'validate-showcase.js'), file], {
      cwd: directory, encoding: 'utf8',
    });
    const source = fs.readFileSync(file, 'utf8');
    assert.match(source, /products: \[decisions-api\]/);
    const accepted = validate();
    assert.equal(accepted.status, 0, accepted.stdout + accepted.stderr);
    for (const product of ['sonar-api', 'unknown-api']) {
      fs.writeFileSync(file, source.replace('[decisions-api]', `[${product}]`));
      const rejected = validate();
      assert.notEqual(rejected.status, 0);
      assert.match(rejected.stderr, new RegExp(product));
    }
    for (const expression of ['{\nMath.max(1, 2)\n}', '<Note title={\nMath.max(1, 2)\n}>Text</Note>', '<Note {...{title: "Text"}}>Text</Note>', 'export const value = 1']) {
      fs.writeFileSync(file, `${source}\n${expression}\n`);
      const rejected = validate();
      assert.notEqual(rejected.status, 0);
      assert.match(rejected.stderr, /executable expressions/);
    }
    fs.writeFileSync(file, `${source}\n\`{example}\`\n\n\`\`\`js\n{\nMath.max(1, 2)\n}\n\`\`\`\n`);
    const codeExample = validate();
    assert.equal(codeExample.status, 0, codeExample.stdout + codeExample.stderr);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
