# Harnais de rendu Chromium — vague 1, file D

Sert à vérifier **dans un navigateur** ce qu'un test de module ne peut pas
voir : qu'un élément est réellement rendu, visible, et placé où il doit
l'être. Ajouté pour GL-19 (mentions IA, article 50 de l'AI Act).

Ce n'est pas une page de l'application : elle n'est pas routée, et
`npm run build` ne la construit pas (point d'entrée distinct). Les appels
réseau des composants y sont neutralisés — ce qui est vérifié est le rendu,
pas le transport.

## Jouer le contrôle

```bash
cd frontend
export PATH=/opt/node22/bin:$PATH
npx vite build --base ./ --outDir dist-harness --emptyOutDir tests/harness
cd tests/harness/dist-harness && npx http-server -p 8199 -s . &
node chk_gl19.mjs      # script Playwright, reproduit dans le rapport de file
```

Le `file://` ne suffit pas : Chromium refuse les modules ES chargés depuis ce
protocole (CORS). Il faut servir le répertoire en HTTP local.

Vues disponibles via `?vue=` : `studio` (`ChatSidebarStudio`), `legacy`
(`ChatSidebar`), `banner` (le bandeau seul).

`dist-harness/` est un artefact de build : il n'est pas suivi par git.
