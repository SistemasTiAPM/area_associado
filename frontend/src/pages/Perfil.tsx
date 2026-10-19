import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import {
  atualizarContato,
  confirmarTrocaEmail,
  enviarFoto,
  iniciarTrocaEmail,
  obterPerfil,
  removerFoto,
  urlReautenticacao,
  type CamposContato,
  type Endereco,
  type PedidoCodigo,
  type Perfil,
} from '../api/perfil';
import { ConteudoAvatar } from '../components/Avatar';
import { Campo } from '../components/Campo';
import { EstadoVazio } from '../components/EstadoVazio';
import { dataBR } from '../lib/formato';
import { useSessao } from '../state/SessaoContext';
import { useToast } from '../state/ToastContext';

const FOTO_MAX_BYTES = 5 * 1024 * 1024;
const REENVIO_S = 60;
const UFS = 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split(' ');

type Erros = Record<string, string>;

/** Erros de campo vindos da API (`detalhes`), indexados pelo caminho ("endereco.cep"). */
function errosDe(falha: unknown): Erros {
  if (!(falha instanceof ApiError) || !falha.detalhes) return {};
  return Object.fromEntries(falha.detalhes.map((d) => [d.campo, d.mensagem]));
}

/* ------------------------------------------------------------------- foto */
function SecaoFoto({ perfil, aoMudar }: { perfil: Perfil; aoMudar: (versao: string | null) => void }) {
  const { sessao, recarregar } = useSessao();
  const { mostrar, mostrarErro } = useToast();
  const entrada = useRef<HTMLInputElement>(null);
  const [ocupado, setOcupado] = useState(false);

  const aoEscolher = async (evento: ChangeEvent<HTMLInputElement>) => {
    const arquivo = evento.target.files?.[0];
    evento.target.value = '';
    if (!arquivo) return;
    if (arquivo.size > FOTO_MAX_BYTES) {
      mostrarErro(new ApiError(413, 'arquivo_grande', 'A foto deve ter até 5 MB.'));
      return;
    }
    setOcupado(true);
    try {
      const r = await enviarFoto(arquivo);
      aoMudar(r.foto_versao);
      mostrar('Foto atualizada');
      await recarregar();
    } catch (falha) {
      mostrarErro(falha);
    } finally {
      setOcupado(false);
    }
  };

  const aoRemover = async () => {
    setOcupado(true);
    try {
      await removerFoto();
      aoMudar(null);
      mostrar('Foto removida');
      await recarregar();
    } catch (falha) {
      mostrarErro(falha);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section className="cartao secao-perfil" aria-labelledby="titulo-foto">
      <h2 className="secao__titulo" id="titulo-foto">
        Foto
      </h2>
      <div className="foto-perfil">
        <span className="avatar avatar--96">
          <ConteudoAvatar iniciais={sessao.associado.iniciais} fotoVersao={perfil.foto_versao} tamanho={96} />
        </span>
        <div className="botoes">
          <input
            ref={entrada}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(e) => void aoEscolher(e)}
            aria-hidden="true"
            tabIndex={-1}
          />
          <button type="button" className="botao botao--primario" disabled={ocupado} onClick={() => entrada.current?.click()}>
            {perfil.tem_foto ? 'Trocar foto' : 'Enviar foto'}
          </button>
          {perfil.tem_foto ? (
            <button type="button" className="botao botao--secundario" disabled={ocupado} onClick={() => void aoRemover()}>
              Remover foto
            </button>
          ) : null}
        </div>
      </div>
      <p className="secao__subtitulo">JPG, PNG ou WebP de até 5 MB. A foto é recortada em quadrado e vai para o seu cadastro na APM.</p>
    </section>
  );
}

/* --------------------------------------------------------------- cadastro */
function SecaoCadastro({ perfil }: { perfil: Perfil }) {
  const crm = perfil.crm ? `${perfil.crm}${perfil.crm_uf ? ` · ${perfil.crm_uf}` : ''}` : '—';
  const filiacao = perfil.data_filiacao ? dataBR(new Date(`${perfil.data_filiacao}T12:00:00Z`)) : '—';
  return (
    <section className="cartao secao-perfil" aria-labelledby="titulo-cadastro">
      <h2 className="secao__titulo" id="titulo-cadastro">
        Dados do cadastro
      </h2>
      <dl className="dados-perfil">
        <dt>Nome</dt>
        <dd>{perfil.nome ?? '—'}</dd>
        <dt>CRM</dt>
        <dd>{crm}</dd>
        <dt>Tipo de associado</dt>
        <dd>{perfil.tipo_associado ?? '—'}</dd>
        <dt>Situação</dt>
        <dd>{perfil.status_associativo ?? '—'}</dd>
        <dt>Associado desde</dt>
        <dd>{filiacao}</dd>
        <dt>Nº de contato</dt>
        <dd>{perfil.num_contato ?? '—'}</dd>
      </dl>
      <p className="secao__subtitulo">Para corrigir estes dados, fale com a Central de Relacionamento.</p>
    </section>
  );
}

/* ---------------------------------------------------------------- contato */
const ENDERECO_VAZIO: Endereco = { logradouro: '', numero: '', complemento: '', bairro: '', cidade: '', uf: 'SP', cep: '' };

function SecaoContato({ perfil, aoAtualizar }: { perfil: Perfil; aoAtualizar: (p: Perfil) => void }) {
  const { mostrar, mostrarErro } = useToast();
  const [celular, setCelular] = useState(perfil.celular ?? '');
  const [telefone, setTelefone] = useState(perfil.telefone ?? '');
  const [telefone2, setTelefone2] = useState(perfil.telefone2 ?? '');
  // Estado inicial do formulário = referência para saber se o endereço mudou.
  const [enderecoInicial] = useState<Endereco>(() => ({
    ...ENDERECO_VAZIO,
    ...perfil.endereco,
    complemento: perfil.endereco?.complemento ?? '',
  }));
  const [endereco, setEndereco] = useState<Endereco>(enderecoInicial);
  const [erros, setErros] = useState<Erros>({});
  const [salvando, setSalvando] = useState(false);

  const mudouEndereco = (Object.keys(ENDERECO_VAZIO) as (keyof Endereco)[]).some(
    (k) => (endereco[k] ?? '').trim() !== (enderecoInicial[k] ?? '').trim(),
  );

  const aoSalvar = async (evento: FormEvent) => {
    evento.preventDefault();
    const campos: CamposContato = {};
    if (celular.trim() !== (perfil.celular ?? '')) campos.celular = celular.trim();
    if (telefone.trim() !== (perfil.telefone ?? '')) campos.telefone = telefone.trim() || null;
    if (telefone2.trim() !== (perfil.telefone2 ?? '')) campos.telefone2 = telefone2.trim() || null;
    if (perfil.endereco_disponivel && mudouEndereco) {
      campos.endereco = { ...endereco, complemento: endereco.complemento?.trim() || null };
    }
    if (Object.keys(campos).length === 0) {
      mostrar('Nada para salvar');
      return;
    }
    setSalvando(true);
    setErros({});
    try {
      aoAtualizar(await atualizarContato(campos));
      mostrar('Dados atualizados');
    } catch (falha) {
      setErros(errosDe(falha));
      mostrarErro(falha);
      if (falha instanceof ApiError && falha.erro === 'endereco_indisponivel') {
        // O CRM deixou de aceitar endereço: recarrega para esconder o formulário dele.
        try {
          aoAtualizar(await obterPerfil());
        } catch {
          /* o aviso do erro já foi mostrado */
        }
      }
    } finally {
      setSalvando(false);
    }
  };

  const campoEndereco = (chave: keyof Endereco, rotulo: string, autoComplete: string) => (
    <Campo id={`end-${chave}`} rotulo={rotulo} erro={erros[`endereco.${chave}`]}>
      {(a) => (
        <input
          {...a}
          className="campo__entrada"
          autoComplete={autoComplete}
          value={endereco[chave] ?? ''}
          onChange={(e) => setEndereco({ ...endereco, [chave]: e.target.value })}
        />
      )}
    </Campo>
  );

  return (
    <section className="cartao secao-perfil" aria-labelledby="titulo-contato">
      <h2 className="secao__titulo" id="titulo-contato">
        Contato
      </h2>
      <form className="formulario" onSubmit={(e) => void aoSalvar(e)} noValidate>
        <div className="grade-campos">
          <Campo id="celular" rotulo="Celular" erro={erros.celular} dica="Com DDD, ex.: (11) 91234-5678">
            {(a) => (
              <input {...a} className="campo__entrada" type="tel" inputMode="tel" autoComplete="tel"
                value={celular} onChange={(e) => setCelular(e.target.value)} required />
            )}
          </Campo>
          <Campo id="telefone" rotulo="Telefone (opcional)" erro={erros.telefone}>
            {(a) => (
              <input {...a} className="campo__entrada" type="tel" inputMode="tel" value={telefone}
                onChange={(e) => setTelefone(e.target.value)} />
            )}
          </Campo>
          <Campo id="telefone2" rotulo="Outro telefone (opcional)" erro={erros.telefone2}>
            {(a) => (
              <input {...a} className="campo__entrada" type="tel" inputMode="tel" value={telefone2}
                onChange={(e) => setTelefone2(e.target.value)} />
            )}
          </Campo>
        </div>
        {perfil.endereco_disponivel ? (
          <fieldset className="grupo-campos">
            <legend className="grupo-campos__titulo">Endereço</legend>
            <div className="grade-campos">
              {campoEndereco('cep', 'CEP', 'postal-code')}
              {campoEndereco('logradouro', 'Logradouro', 'address-line1')}
              {/* Não há token de autocomplete para o número; complemento é a 2ª linha (address1_line2 no CRM). */}
              {campoEndereco('numero', 'Número', 'off')}
              {campoEndereco('complemento', 'Complemento (opcional)', 'address-line2')}
              {campoEndereco('bairro', 'Bairro', 'address-level3')}
              {campoEndereco('cidade', 'Cidade', 'address-level2')}
              <Campo id="end-uf" rotulo="UF" erro={erros['endereco.uf']}>
                {(a) => (
                  <select {...a} className="campo__entrada" autoComplete="address-level1" value={endereco.uf}
                    onChange={(e) => setEndereco({ ...endereco, uf: e.target.value })}>
                    {UFS.map((uf) => (
                      <option key={uf} value={uf}>
                        {uf}
                      </option>
                    ))}
                  </select>
                )}
              </Campo>
            </div>
          </fieldset>
        ) : (
          <div className="grupo-campos" role="group" aria-labelledby="titulo-endereco">
            <h3 className="grupo-campos__titulo" id="titulo-endereco">
              Endereço
            </h3>
            <p className="aviso">
              O endereço ainda não pode ser alterado por aqui. Para corrigir, fale com a Central de Relacionamento.
            </p>
          </div>
        )}
        <div className="botoes">
          <button type="submit" className="botao botao--primario" disabled={salvando}>
            {salvando ? 'Salvando…' : 'Salvar alterações'}
          </button>
        </div>
      </form>
    </section>
  );
}

/* ----------------------------------------------------------------- e-mail */
type FaseEmail = 'inicial' | 'novo' | 'codigo';

function SecaoEmail({ perfil, aoAtualizar }: { perfil: Perfil; aoAtualizar: (p: Perfil) => void }) {
  const { mostrar, mostrarErro } = useToast();
  const [fase, setFase] = useState<FaseEmail>('inicial');
  const [novo, setNovo] = useState('');
  const [codigo, setCodigo] = useState('');
  const [pedido, setPedido] = useState<PedidoCodigo | null>(null);
  const [precisaReauth, setPrecisaReauth] = useState(perfil.email_exige_reautenticacao);
  const [espera, setEspera] = useState(0);
  const [erros, setErros] = useState<Erros>({});
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    if (espera <= 0) return;
    const t = setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [espera]);

  const tratar = (falha: unknown) => {
    if (falha instanceof ApiError && falha.erro === 'reautenticacao_necessaria') setPrecisaReauth(true);
    setErros(errosDe(falha));
    mostrarErro(falha);
  };

  const pedirCodigo = async (evento?: FormEvent) => {
    evento?.preventDefault();
    setOcupado(true);
    setErros({});
    try {
      setPedido(await iniciarTrocaEmail(novo.trim()));
      setFase('codigo');
      setEspera(REENVIO_S);
      mostrar('Código enviado');
    } catch (falha) {
      tratar(falha);
    } finally {
      setOcupado(false);
    }
  };

  const confirmar = async (evento: FormEvent) => {
    evento.preventDefault();
    setOcupado(true);
    setErros({});
    try {
      aoAtualizar(await confirmarTrocaEmail(novo.trim(), codigo.trim()));
      setFase('inicial');
      setNovo('');
      setCodigo('');
      setPedido(null);
      mostrar('E-mail atualizado');
    } catch (falha) {
      tratar(falha);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section className="cartao secao-perfil" aria-labelledby="titulo-email">
      <h2 className="secao__titulo" id="titulo-email">
        E-mail de acesso
      </h2>
      <p className="email-atual">{perfil.email ?? 'Nenhum e-mail cadastrado'}</p>
      <p className="secao__subtitulo">
        É para este e-mail que o Login APM envia os códigos de primeiro acesso e de recuperação de senha.
      </p>

      {fase === 'inicial' ? (
        <div className="botoes">
          <button type="button" className="botao botao--secundario" onClick={() => setFase('novo')}>
            Alterar e-mail
          </button>
        </div>
      ) : precisaReauth ? (
        <div className="aviso" role="status">
          <p>Por segurança, confirme sua senha no Login APM antes de trocar o e-mail. Você volta para esta página em seguida.</p>
          <div className="botoes">
            <a className="botao botao--primario" href={urlReautenticacao()}>
              Confirmar minha identidade
            </a>
            <button type="button" className="botao botao--secundario" onClick={() => setFase('inicial')}>
              Cancelar
            </button>
          </div>
        </div>
      ) : fase === 'novo' ? (
        <form className="formulario" onSubmit={(e) => void pedirCodigo(e)} noValidate>
          <Campo id="email-novo" rotulo="Novo e-mail" erro={erros.email}>
            {(a) => (
              <input {...a} className="campo__entrada" type="email" autoComplete="email" inputMode="email"
                value={novo} onChange={(e) => setNovo(e.target.value)} required />
            )}
          </Campo>
          <div className="botoes">
            <button type="submit" className="botao botao--primario" disabled={ocupado || !novo.trim()}>
              Enviar código
            </button>
            <button type="button" className="botao botao--secundario" onClick={() => setFase('inicial')}>
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <form className="formulario" onSubmit={(e) => void confirmar(e)} noValidate>
          <p role="status">
            Enviamos um código de 6 dígitos para <strong>{pedido?.enviado_para}</strong>. Ele vale por 10 minutos.
          </p>
          {pedido?.codigo_teste ? (
            <p className="aviso">Ambiente de construção (e-mail simulado): o código é {pedido.codigo_teste}.</p>
          ) : null}
          <Campo id="email-codigo" rotulo="Código" erro={erros.codigo}>
            {(a) => (
              <input {...a} className="campo__entrada campo__entrada--codigo" inputMode="numeric" autoComplete="one-time-code"
                pattern="[0-9]{6}" maxLength={6} value={codigo}
                onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))} required />
            )}
          </Campo>
          <div className="botoes">
            <button type="submit" className="botao botao--primario" disabled={ocupado || codigo.length !== 6}>
              Confirmar
            </button>
            <button type="button" className="botao botao--secundario" disabled={ocupado || espera > 0}
              onClick={() => void pedirCodigo()}>
              {espera > 0 ? `Reenviar código (${espera}s)` : 'Reenviar código'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ tela */
type Estado = { fase: 'carregando' } | { fase: 'erro' } | { fase: 'pronto'; perfil: Perfil };

/** Meu perfil (RF-PE, tela nova — sem layout na spec, tokens e componentes dela). */
export function PaginaPerfil() {
  const { mostrarErro } = useToast();
  const [estado, setEstado] = useState<Estado>({ fase: 'carregando' });

  const carregar = useCallback(async () => {
    setEstado({ fase: 'carregando' });
    try {
      setEstado({ fase: 'pronto', perfil: await obterPerfil() });
    } catch (falha) {
      mostrarErro(falha);
      setEstado({ fase: 'erro' });
    }
  }, [mostrarErro]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (estado.fase === 'carregando') {
    return (
      <p className="carregando" role="status" aria-busy="true">
        Carregando seu perfil…
      </p>
    );
  }
  if (estado.fase === 'erro') {
    return (
      <EstadoVazio titulo="Não foi possível carregar seu perfil">
        <p>Tente novamente em instantes.</p>
        <button type="button" className="botao botao--primario" onClick={() => void carregar()}>
          Tentar novamente
        </button>
      </EstadoVazio>
    );
  }

  const perfil = estado.perfil;
  const atualizar = (p: Perfil) => setEstado({ fase: 'pronto', perfil: p });
  return (
    <>
      {perfil.desatualizado ? (
        <p className="aviso" role="status">
          Não conseguimos consultar seu cadastro agora. Mostramos os últimos dados guardados; alterações ficam
          indisponíveis até a conexão voltar.
        </p>
      ) : null}
      <div className="grade-perfil">
        <SecaoFoto perfil={perfil} aoMudar={(versao) => atualizar({ ...perfil, tem_foto: versao !== null, foto_versao: versao })} />
        <SecaoCadastro perfil={perfil} />
        <SecaoContato key={perfil.atualizado_em ?? 'contato'} perfil={perfil} aoAtualizar={atualizar} />
        <SecaoEmail perfil={perfil} aoAtualizar={atualizar} />
      </div>
    </>
  );
}
