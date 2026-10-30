/**
 * Links externos (RF-SH-12): só `https:` e só para hosts permitidos. Qualquer
 * outra coisa (javascript:, http:, data:, host desconhecido, URL malformada)
 * devolve `null` — o componente então não renderiza o link.
 */

export const HOSTS_EXTERNOS_PERMITIDOS: readonly string[] = [
  'wa.me',
  'clubapm.com.br',
  'www.clubapm.com.br',
  'apm.org.br',
  'www.apm.org.br',
  'totalpass.apm.org.br',
  'login.apm.org.br',
];

export function urlExternaSegura(bruta: string, hosts: readonly string[] = HOSTS_EXTERNOS_PERMITIDOS): string | null {
  let url: URL;
  try {
    url = new URL(bruta);
  } catch (falha) {
    if (falha instanceof TypeError) return null;
    throw falha;
  }
  if (url.protocol !== 'https:' || url.username || url.password) return null;
  if (!hosts.includes(url.hostname.toLowerCase())) return null;
  return url.toString();
}

/** Mensagem pré-preenchida da Central APM — proposta (REQUISITOS LA-18); sem exclamação (spec v2 §3.3). */
export const MENSAGEM_CENTRAL = 'Olá. Vim pela Minha APM e preciso de ajuda.';

export function urlWhatsapp(numero: string, mensagem: string): string | null {
  if (!/^[1-9][0-9]{9,14}$/.test(numero)) return null;
  return urlExternaSegura(`https://wa.me/${numero}?text=${encodeURIComponent(mensagem)}`);
}

/**
 * Link de telefone (RF-AJ-02; `tel:` na allowlist de esquemas): só `tel:` seguido
 * de `+` opcional e 8 a 15 dígitos (E.164 sem separadores). Aceita também só os
 * dígitos. Qualquer outra coisa (letras, `;ext=`, parâmetros, `javascript:`) → `null`.
 */
export function urlTelefone(bruta: string): string | null {
  const valor = bruta.trim();
  const numero = valor.toLowerCase().startsWith('tel:') ? valor.slice(4) : valor;
  if (!/^\+?[0-9]{8,15}$/.test(numero)) return null;
  return `tel:${numero}`;
}
