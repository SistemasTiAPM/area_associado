/* Marca o documento como "JS ativo" antes de o CSS pintar a tela.
   Com a classe `js`, `html.js .alert { display: none }` esconde os avisos em
   HTML — eles passam a ser exibidos pelo SweetAlert2 (base.html). Sem JS a
   classe não entra e os avisos continuam visíveis: degradação graciosa.
   Carregado síncrono no <head> justamente para não haver flash do bloco. */
document.documentElement.className += ' js';
