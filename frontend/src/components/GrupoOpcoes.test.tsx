import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { CheckboxGroup, RadioGroup } from './GrupoOpcoes';

const MOTIVOS = [
  { valor: 'custo', rotulo: 'Custo da contribuição' },
  { valor: 'uso', rotulo: 'Uso pouco os benefícios', descricao: 'Conte o que faria diferença.' },
  { valor: 'outro', rotulo: 'Outro motivo', desabilitada: true },
] as const;

type Motivo = (typeof MOTIVOS)[number]['valor'];

describe('RadioGroup', () => {
  it('fieldset com legenda, radios nativos, dica e erro ligados por aria-describedby', () => {
    render(<RadioGroup<Motivo> nome="motivo" legenda="Motivo do cancelamento" opcoes={MOTIVOS} valor={null} aoMudar={() => {}} dica="Escolha um." erro="Escolha um motivo para continuar." />);
    const grupo = screen.getByRole('group', { name: 'Motivo do cancelamento' });
    expect(grupo).toHaveAttribute('aria-invalid', 'true');
    expect(grupo.getAttribute('aria-describedby')).toBe('motivo-dica motivo-erro');
    expect(screen.getByRole('alert')).toHaveTextContent('Escolha um motivo para continuar.');
    expect(within(grupo).getAllByRole('radio')).toHaveLength(3);
    expect(screen.getByRole('radio', { name: 'Outro motivo' })).toBeDisabled();
    expect(screen.getByRole('radio', { name: /Uso pouco/ })).toHaveAccessibleDescription('Conte o que faria diferença.');
  });

  it('escolher chama aoMudar com o valor; só um marcado', async () => {
    const usuario = userEvent.setup();
    function Harness() {
      const [valor, setValor] = useState<Motivo | null>(null);
      return <RadioGroup<Motivo> nome="motivo" legenda="Motivo" opcoes={MOTIVOS} valor={valor} aoMudar={setValor} />;
    }
    render(<Harness />);
    await usuario.click(screen.getByRole('radio', { name: 'Custo da contribuição' }));
    expect(screen.getByRole('radio', { name: 'Custo da contribuição' })).toBeChecked();
    await usuario.click(screen.getByRole('radio', { name: /Uso pouco/ }));
    expect(screen.getByRole('radio', { name: 'Custo da contribuição' })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /Uso pouco/ })).toBeChecked();
  });
});

describe('CheckboxGroup', () => {
  it('alterna valores e devolve a lista na ordem das opções', async () => {
    const usuario = userEvent.setup();
    const aoMudar = vi.fn();
    function Harness() {
      const [valores, setValores] = useState<Motivo[]>([]);
      return (
        <CheckboxGroup<Motivo>
          nome="areas"
          legenda="Áreas de atuação"
          legendaOculta
          opcoes={MOTIVOS}
          valores={valores}
          aoMudar={(v) => {
            aoMudar(v);
            setValores(v);
          }}
        />
      );
    }
    render(<Harness />);
    expect(screen.getByRole('group', { name: 'Áreas de atuação' })).toBeInTheDocument();
    await usuario.click(screen.getByRole('checkbox', { name: /Uso pouco/ }));
    await usuario.click(screen.getByRole('checkbox', { name: 'Custo da contribuição' }));
    expect(aoMudar).toHaveBeenLastCalledWith(['custo', 'uso']);
    await usuario.click(screen.getByRole('checkbox', { name: /Uso pouco/ }));
    expect(aoMudar).toHaveBeenLastCalledWith(['custo']);
    expect(screen.getByRole('checkbox', { name: 'Custo da contribuição' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /Uso pouco/ })).not.toBeChecked();
  });

  it('sem erro não há aria-invalid nem alerta', () => {
    render(<CheckboxGroup nome="x" legenda="X" opcoes={MOTIVOS} valores={[]} aoMudar={() => {}} />);
    expect(screen.getByRole('group')).not.toHaveAttribute('aria-invalid');
    expect(screen.getByRole('group')).not.toHaveAttribute('aria-describedby');
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
