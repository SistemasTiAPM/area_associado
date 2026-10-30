import { Component, type ReactNode } from 'react';
import { registrarUso } from '../lib/analytics';
import { EstadoErro } from './EstadoErro';

interface Estado {
  falhou: boolean;
}

/**
 * Limite de erro das páginas carregadas sob demanda (`React.lazy`). Se o pedaço
 * da página não chega (deploy trocou os arquivos, rede caiu), a tela mostra o
 * que fazer em vez de derrubar o shell; registra `erro_js` sem mensagem nem stack.
 */
export class LimiteCargaPagina extends Component<{ children: ReactNode }, Estado> {
  override state: Estado = { falhou: false };

  static getDerivedStateFromError(): Estado {
    return { falhou: true };
  }

  override componentDidCatch(falha: unknown): void {
    console.error(falha);
    registrarUso({ acao: 'erro_js', entidade: 'rota', entidade_id: '/area', detalhes: { tipo: 'carga_pagina' } });
  }

  override render(): ReactNode {
    if (!this.state.falhou) return this.props.children;
    return (
      <EstadoErro
        titulo="Não conseguimos abrir esta página"
        mensagem="Pode ser a conexão ou uma atualização da Minha APM. Recarregue a página para tentar de novo."
        rotuloBotao="Recarregar a página"
        aoTentarNovamente={() => window.location.reload()}
      />
    );
  }
}
