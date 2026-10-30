import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ImagemSegura, urlImagemSegura } from './ImagemSegura';

const HOSTS = ['https://www.apm.org.br', 'cdn.clubapm.com.br'];

describe('urlImagemSegura', () => {
  it.each([
    'http://www.apm.org.br/logo.png',
    'https://evil.example.com/logo.png',
    'https://www.apm.org.br.evil.com/logo.png',
    'https://user:senha@www.apm.org.br/logo.png',
    'data:image/png;base64,AAAA',
    'javascript:alert(1)',
    '//www.apm.org.br/logo.png',
    '/static/../x y.png',
    '',
    '   ',
    'não é url',
  ])('recusa %s', (url) => {
    expect(urlImagemSegura(url, HOSTS)).toBeNull();
  });

  it('aceita https em host permitido (origem ou host puro, sem distinção de caixa) e caminho relativo', () => {
    expect(urlImagemSegura('https://WWW.APM.ORG.BR/wp-content/logo.png', HOSTS)).toBe('https://www.apm.org.br/wp-content/logo.png');
    expect(urlImagemSegura('https://cdn.clubapm.com.br/a.jpg?v=2', HOSTS)).toBe('https://cdn.clubapm.com.br/a.jpg?v=2');
    expect(urlImagemSegura('/api/v1/perfil/foto?v=abc', HOSTS)).toBe('/api/v1/perfil/foto?v=abc');
    expect(urlImagemSegura('/api/v1/perfil/foto', HOSTS, false)).toBeNull();
    expect(urlImagemSegura(null, HOSTS)).toBeNull();
    expect(urlImagemSegura(undefined, HOSTS)).toBeNull();
  });

  it('entradas inválidas na lista são ignoradas, não abrem brecha', () => {
    expect(urlImagemSegura('https://x.example/a.png', ['http://x.example', '*', ''])).toBeNull();
  });
});

describe('ImagemSegura', () => {
  it('host permitido: img lazy, async, sem referrer, dentro de caixa com proporção fixa', () => {
    const { container } = render(<ImagemSegura src="https://www.apm.org.br/capa.jpg" alt="Capa do congresso" hostsPermitidos={HOSTS} proporcao="4/3" />);
    const img = screen.getByRole('img', { name: 'Capa do congresso' });
    expect(img).toHaveAttribute('loading', 'lazy');
    expect(img).toHaveAttribute('decoding', 'async');
    expect(img).toHaveAttribute('referrerpolicy', 'no-referrer');
    expect(container.firstChild).toHaveClass('imagem-segura--4-3');
  });

  it('host fora da lista: placeholder acessível, nenhum <img> no DOM', () => {
    const { container } = render(<ImagemSegura src="https://evil.example.com/x.png" alt="Logo do parceiro" hostsPermitidos={HOSTS} />);
    expect(container.querySelector('img')).toBeNull();
    const placeholder = screen.getByRole('img', { name: 'Logo do parceiro' });
    expect(placeholder).toHaveClass('imagem-segura--placeholder');
    expect(placeholder).toHaveAttribute('data-motivo', 'host_nao_permitido');
  });

  it('decorativa (alt vazio) fica fora da árvore de acessibilidade', () => {
    const { container } = render(<ImagemSegura src="https://nao.permitido/x.png" alt="" hostsPermitidos={HOSTS} />);
    expect(screen.queryByRole('img')).toBeNull();
    expect(container.firstChild).toHaveAttribute('aria-hidden', 'true');
  });

  it('falha de carregamento vira placeholder; src nova reinicia', () => {
    const { container, rerender } = render(<ImagemSegura src="https://www.apm.org.br/a.jpg" alt="A" hostsPermitidos={HOSTS} />);
    fireEvent.error(container.querySelector('img') as HTMLImageElement);
    expect(screen.getByRole('img', { name: 'A' })).toHaveAttribute('data-motivo', 'falha_carregamento');
    rerender(<ImagemSegura src="https://www.apm.org.br/b.jpg" alt="B" hostsPermitidos={HOSTS} />);
    expect(container.querySelector('img')).toHaveAttribute('src', 'https://www.apm.org.br/b.jpg');
  });
});
