import { lstatSync } from 'node:fs';
import { delimiter, join } from 'node:path';

try {
  try {
    import.meta.resolve('@anthropic-ai/claude-agent-sdk');
    throw new Error('CI_UNEXPECTED_AI_PACKAGE');
  } catch (error) {
    if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error;
  }
  if (!process.env.PATH) throw new Error('CI_PATH_UNAVAILABLE');
  for (const executable of ['codex', 'bwrap']) {
    for (const directory of process.env.PATH.split(delimiter)) {
      try { lstatSync(join(directory, executable)); }
      catch (error) {
        if (error.code === 'ENOENT') continue;
        throw new Error('CI_PATH_INSPECTION_FAILED');
      }
      throw new Error(`CI_UNEXPECTED_AI_EXECUTABLE:${executable}`);
    }
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
