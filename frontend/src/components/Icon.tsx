/**
 * Ícones SVG de linha próprios (spec "Componentes": viewBox 24, stroke 1.8,
 * linecap/linejoin round, currentColor). Sem icon-font, sem CDN (ADR-0001).
 * Decorativos por padrão (`aria-hidden`); o rótulo acessível fica no controle.
 */

const CAMINHOS = {
  inicio: ['M3 10.5 12 3l9 7.5', 'M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5'],
  sacola: ['M6 7h12l1 13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1L6 7z', 'M9 7V6a3 3 0 0 1 6 0v1'],
  presente: ['M4 11h16v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-9z', 'M3 7h18v4H3z', 'M12 7v14', 'M12 7C10.5 4 7 3.5 7 6s3 1 5 1zm0 0c1.5-3 5-3.5 5-1s-3 1-5 1z'],
  jornal: ['M4 5h13v14a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2V5z', 'M17 9h3v10a2 2 0 0 1-2 2', 'M8 9h5', 'M8 13h5', 'M8 17h3'],
  recibo: ['M6 3h12v18l-3-2-3 2-3-2-3 2V3z', 'M9 8h6', 'M9 12h6', 'M9 16h4'],
  usuario: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4 21a8 8 0 0 1 16 0'],
  pessoas: ['M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M2 21a7 7 0 0 1 14 0', 'M16 3.5a4 4 0 0 1 0 7', 'M18 14.5a7 7 0 0 1 4 6.5'],
  calendario: ['M5 5h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z', 'M8 3v4', 'M16 3v4', 'M4 10h16'],
  cartao: ['M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z', 'M3 10h18', 'M7 15h4'],
  estrela: ['M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3z'],
  caixa: ['M4 13l2.5-7h11L20 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-6z', 'M4 13h4.5l1 2h5l1-2H20'],
  busca: ['M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z', 'M20 20l-4-4'],
  fechar: ['M6 6l12 12', 'M18 6 6 18'],
  menu: ['M4 7h16', 'M4 12h16', 'M4 17h16'],
  check: ['M5 12.5l4.5 4.5L19 7.5'],
  alerta: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 8v5', 'M12 16.5v.01'],
  conversa: ['M20 12a8 8 0 0 1-11.7 7.1L4 20l1-4.1A8 8 0 1 1 20 12z'],
  sair: ['M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3', 'M10 8l-4 4 4 4', 'M6 12h10'],
  escudo: ['M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3z'],
  voltar: ['M15 6l-6 6 6 6'],
  externo: ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'],
} as const satisfies Record<string, readonly string[]>;

export type NomeIcone = keyof typeof CAMINHOS;

export function Icon({ nome, tamanho = 18 }: { nome: NomeIcone; tamanho?: number }) {
  return (
    <svg
      className="icone"
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {CAMINHOS[nome].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
