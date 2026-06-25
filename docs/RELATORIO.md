# Relatório do Projeto

## Objetivos

O objetivo do Youtube Summarizer foi construir uma automação privada para
acompanhar a página de inscrições do YouTube em uma conta Google autenticada,
identificar vídeos recentes, enviar cada URL para o site do Gemini e armazenar o
resumo gerado em um banco SQLite local. A automação deveria funcionar em
ambiente de homelab sem interface gráfica permanente, usando Python, `uv`,
Playwright e Docker.

Também era necessário manter histórico dos vídeos já processados para evitar
resumos duplicados. Para isso, cada vídeo é normalizado pelo ID do YouTube e
gravado com seu status: pendente, resumido ou falho. Vídeos já resumidos são
ignorados em execuções futuras, enquanto vídeos pendentes ou com falha podem ser
tentados novamente.

Outro objetivo importante foi documentar a operação para que um agente, como o
Hermes, consiga administrar o fluxo no homelab. A documentação cobre o processo
de autenticação, comandos normais de execução, cuidados de segurança e passos de
diagnóstico.

## Abordagem

A solução foi implementada como uma CLI Python simples, sem framework, com
módulos separados por responsabilidade. O módulo de configuração lê variáveis de
ambiente e produz configurações tipadas. O módulo de browser cria um contexto
persistente do Playwright usando o mesmo perfil de navegador em todas as
execuções. O módulo do YouTube acessa a página de inscrições, extrai URLs de
vídeos recentes e normaliza os links. O módulo do Gemini envia o prompt com a
URL do vídeo e aguarda uma resposta estável. O módulo de banco de dados gerencia
o SQLite, enquanto o workflow coordena a execução completa.

Para resolver o problema de autenticação em servidor sem GUI, foi criado um modo
temporário de login via Docker/noVNC. O serviço `auth-server` sobe Xvfb,
openbox, x11vnc e websockify, expondo uma interface VNC local em
`http://localhost:6080/vnc.html`. Nessa tela, o usuário faz login manualmente em
uma instância real do Google Chrome. Depois disso, a automação usa Playwright com
o mesmo perfil persistente, reaproveitando os cookies e o estado da conta Google.

O projeto usa volumes Docker separados para estado persistente. O volume
`/browser-profile` guarda a sessão Google e o volume `/data` guarda o banco
SQLite, logs JSON e screenshots de falhas. Essa separação permite atualizar a
imagem da aplicação sem perder autenticação nem histórico.

## Desafios Enfrentados

O primeiro desafio foi o login Google. Navegadores controlados diretamente por
Playwright podem ser bloqueados ou classificados como ambiente automatizado pelo
Google. A solução adotada foi separar a etapa de autenticação da etapa de
automação: o login é feito em um Chrome real, iniciado sem controle do
Playwright, e a automação posterior apenas reutiliza o perfil salvo.

Outro desafio foi operar em um homelab sem interface gráfica. Para isso, a
imagem Docker inclui uma pilha gráfica mínima baseada em Xvfb e noVNC. O acesso
ao navegador fica restrito a `127.0.0.1:6080`, podendo ser encaminhado por SSH ou
Tailscale. Isso evita expor a sessão do navegador publicamente.

Também houve desafios causados pela interface dinâmica do YouTube e do Gemini.
O YouTube mudou a estrutura dos cards da página de inscrições, usando elementos
como `yt-lockup-view-model` e textos em português, como `há 1 hora`. O scraper
foi ajustado para buscar links de vídeo de forma mais genérica, reconhecer
labels em inglês e português e evitar falsos positivos como títulos contendo
frases do tipo `1 hour of music`.

No Gemini, a resposta pode vir com o mesmo texto de uma resposta anterior, por
exemplo em mensagens repetidas de recusa ou indisponibilidade. A lógica inicial
comparava apenas o texto, o que poderia causar timeout mesmo quando uma nova
resposta tivesse sido exibida. A solução foi passar a considerar também a
contagem de elementos de resposta na página.

## Soluções Adotadas

A persistência foi implementada com SQLite por ser suficiente para o volume de
dados esperado e simples de operar no homelab. O schema registra vídeos,
resumos, erros e execuções. Com isso, a automação consegue retomar trabalho,
evitar duplicatas e manter auditoria básica das execuções.

Para proteger o perfil do navegador, foi criado um lock de perfil. Ele impede
que `auth-server`, `auth-check` e `run` usem o mesmo perfil ao mesmo tempo. A
rotina também limpa arquivos de lock antigos do Chromium quando necessário.

Para diagnóstico, a automação registra eventos em JSON e captura screenshots em
falhas de scraping ou de interação com o Gemini. Isso facilita a manutenção
quando YouTube ou Gemini alterarem a interface.

O fluxo final validado foi:

1. subir o navegador de autenticação com `docker compose --profile auth up auth`;
2. fazer login manualmente via noVNC;
3. confirmar acesso com `youtube-summarizer auth-check`;
4. executar `youtube-summarizer run`;
5. listar resultados com `youtube-summarizer list`.

A automação foi testada em execução real: o login foi validado, a página de
inscrições do YouTube foi lida, URLs recentes foram enviadas ao Gemini e os
resumos foram armazenados no SQLite. Também foram executadas as verificações de
qualidade do projeto: formatação com Ruff, lint com Ruff, checagem de tipos com
Mypy e testes automatizados com Pytest.
