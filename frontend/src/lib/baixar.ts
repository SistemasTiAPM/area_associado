/**
 * Salva um objeto como arquivo `.json` no aparelho do associado.
 *
 * Usado só pela exportação dos próprios dados (P13): a rota é POST com CSRF e
 * senha recente, então não pode ser um `<a download>` de mesma origem como os
 * arquivos da carteirinha. O conteúdo vive num Blob em memória apenas durante o
 * clique; nada vai para `localStorage` (RNF-21) e a URL é revogada em seguida.
 */
export function baixarJson(nomeArquivo: string, dados: unknown): void {
  const blob = new Blob([JSON.stringify(dados, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = nomeArquivo;
  link.rel = 'noopener';
  link.hidden = true;
  document.body.appendChild(link);
  try {
    link.click();
  } finally {
    link.remove();
    // Depois do clique: o navegador já iniciou o download a partir do Blob.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}

/** `minha-apm-dados-AAAAMMDD.json`, com a data local do aparelho. */
export function nomeArquivoDados(agora: Date = new Date()): string {
  const dois = (n: number) => String(n).padStart(2, '0');
  return `minha-apm-dados-${agora.getFullYear()}${dois(agora.getMonth() + 1)}${dois(agora.getDate())}.json`;
}
