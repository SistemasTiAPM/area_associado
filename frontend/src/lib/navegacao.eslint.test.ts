// @vitest-environment node
import { ESLint } from 'eslint';
import { describe, expect, it } from 'vitest';

/**
 * A regra de lint da TI-10 é parte da defesa (P-40): este teste prova que ela
 * pega `useNavigate`, `<Navigate>`, `react-router-dom` e `<Link to={variável}>`
 * fora das exceções, e que as exceções (navegacao.ts, LinkInterno, shell) passam.
 */
// cwd padrão = raiz do frontend (onde o Vitest roda): usa o eslint.config.js do projeto.
const eslint = new ESLint();

async function mensagens(codigo: string, arquivo: string): Promise<string[]> {
  const [resultado] = await eslint.lintText(codigo, { filePath: arquivo });
  return (resultado?.messages ?? []).map((m) => `${m.ruleId}: ${m.message}`);
}

describe('lint de navegação (TI-10)', () => {
  it('recusa useNavigate e <Navigate> fora de lib/navegacao.ts e do shell', async () => {
    const codigo = "import { useNavigate } from 'react-router';\nexport const f = () => useNavigate();\n";
    expect((await mensagens(codigo, 'src/pages/Qualquer.tsx')).join('\n')).toMatch(/no-restricted-imports/);
    const nav = "import { Navigate } from 'react-router';\nexport const C = () => <Navigate to=\"/perfil\" />;\n";
    expect((await mensagens(nav, 'src/pages/Qualquer.tsx')).join('\n')).toMatch(/no-restricted-imports/);
  });

  it('recusa react-router-dom em qualquer lugar', async () => {
    const codigo = "import { Link } from 'react-router-dom';\nexport const C = () => <Link to=\"/\">x</Link>;\n";
    expect((await mensagens(codigo, 'src/shell/Qualquer.tsx')).join('\n')).toMatch(/react-router-dom/);
  });

  it('recusa <Link to={variável}> fora das exceções e aceita literal', async () => {
    const variavel = "import { Link } from 'react-router';\nexport const C = ({ d }: { d: string }) => <Link to={d}>x</Link>;\n";
    expect((await mensagens(variavel, 'src/pages/Qualquer.tsx')).join('\n')).toMatch(/LinkInterno/);
    const literal = "import { Link } from 'react-router';\nexport const C = () => <Link to=\"/perfil\">x</Link>;\n";
    expect(await mensagens(literal, 'src/pages/Qualquer.tsx')).toEqual([]);
  });

  it('exceções: shell e LinkInterno podem montar destino a partir de rotas.ts', async () => {
    const codigo = "import { NavLink, useNavigate } from 'react-router';\nexport const C = ({ d }: { d: string }) => { useNavigate(); return <NavLink to={d}>x</NavLink>; };\n";
    expect(await mensagens(codigo, 'src/shell/Qualquer.tsx')).toEqual([]);
  });
});
