import fs from 'fs';
import path from 'path';
import { compile } from '@mdx-js/mdx';

function findMdxFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return findMdxFiles(entryPath);
    }
    return entry.name.endsWith('.mdx') ? [entryPath] : [];
  });
}

async function validateMDX() {
  try {
    const mdxFiles = findMdxFiles('docs').sort();
    
    for (const file of mdxFiles) {
      console.log(`Validating: ${file}`);
      try {
        const content = fs.readFileSync(file, 'utf8');
        await compile(content, { jsx: true });
        console.log(`✅ ${file} - Valid MDX`);
      } catch (error) {
        console.error(`❌ ${file} - MDX Error:`, error.message);
        process.exit(1);
      }
    }
    
    console.log(`\n🎉 All ${mdxFiles.length} MDX files are valid!`);
  } catch (error) {
    console.error('❌ Validation failed:', error.message);
    process.exit(1);
  }
}

validateMDX(); 
