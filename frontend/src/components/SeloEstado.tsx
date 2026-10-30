import { dataBR } from '../lib/formato';
import { Icon, type NomeIcone } from './Icon';

/**
 * Selo de estado de um benefício (spec v2 §8.1: seis estados por associado) e
 * marcações editoriais (§3.2: "novo", "ativo", "patrocinado" e "libera em"
 * sempre com texto, nunca só com cor). Puro: recebe o estado, não consulta API.
 */
export type EstadoSelo =
  | 'disponivel'
  | 'ativo'
  | 'libera_em'
  | 'exclusivo'
  | 'suspenso'
  | 'indisponivel_regiao'
  | 'novo'
  | 'patrocinado';

export const ESTADOS_SELO: readonly EstadoSelo[] = [
  'disponivel',
  'ativo',
  'libera_em',
  'exclusivo',
  'suspenso',
  'indisponivel_regiao',
  'novo',
  'patrocinado',
];

interface Props {
  estado: EstadoSelo;
  /** `libera_em`: data de liberação (fim da carência). Sem data, o texto diz "após a carência". */
  liberaEm?: Date | undefined;
  /** `exclusivo`: categoria que pode usar (padrão da spec: "associado efetivo"). */
  categoria?: string | undefined;
  /** Variante compacta (listas densas). */
  compacto?: boolean;
  className?: string;
}

const ICONES: Record<EstadoSelo, NomeIcone> = {
  disponivel: 'check',
  ativo: 'escudo',
  libera_em: 'relogio',
  exclusivo: 'cadeado',
  suspenso: 'pausa',
  indisponivel_regiao: 'local',
  novo: 'estrela',
  patrocinado: 'megafone',
};

/** Texto de cada estado (voz §3.3: sem exclamação, "associado efetivo", nunca "pagante"). */
export function textoSelo(estado: EstadoSelo, opcoes: { liberaEm?: Date | undefined; categoria?: string | undefined } = {}): string {
  switch (estado) {
    case 'disponivel':
      return 'Disponível';
    case 'ativo':
      return 'Ativo';
    case 'libera_em':
      return opcoes.liberaEm && Number.isFinite(opcoes.liberaEm.getTime())
        ? `Libera em ${dataBR(opcoes.liberaEm)}`
        : 'Libera após a carência';
    case 'exclusivo':
      return `Exclusivo para ${opcoes.categoria?.trim() || 'associado efetivo'}`;
    case 'suspenso':
      return 'Suspenso';
    case 'indisponivel_regiao':
      return 'Indisponível na sua região';
    case 'novo':
      return 'Novo';
    case 'patrocinado':
      return 'Patrocinado';
  }
}

export function SeloEstado({ estado, liberaEm, categoria, compacto = false, className }: Props) {
  const classes = ['selo-estado', `selo-estado--${estado}`, compacto ? 'selo-estado--compacto' : '', className ?? '']
    .filter(Boolean)
    .join(' ');
  return (
    <span className={classes} data-estado={estado}>
      <Icon nome={ICONES[estado]} tamanho={compacto ? 12 : 14} />
      <span className="selo-estado__texto">{textoSelo(estado, { liberaEm, categoria })}</span>
    </span>
  );
}
