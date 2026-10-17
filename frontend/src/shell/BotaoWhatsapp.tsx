import { Icon } from '../components/Icon';
import { LinkExterno } from '../components/LinkExterno';
import { registrarUso } from '../lib/analytics';
import { MENSAGEM_CENTRAL, urlWhatsapp } from '../lib/links';
import { useSessao } from '../state/SessaoContext';

/** "Central APM" (RF-SH-08): número e exibição vêm da configuração do servidor. */
export function BotaoWhatsapp() {
  const { sessao } = useSessao();
  if (!sessao.config.show_whatsapp) return null;
  const url = urlWhatsapp(sessao.config.whatsapp, MENSAGEM_CENTRAL);
  if (url === null) return null;
  return (
    <LinkExterno
      href={url}
      className="fab-whatsapp"
      aoClicar={() => registrarUso({ acao: 'central_whatsapp_abrir', entidade: 'central' })}
    >
      <Icon nome="conversa" tamanho={20} />
      <span>Central APM</span>
    </LinkExterno>
  );
}
