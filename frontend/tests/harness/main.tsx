/**
 * Harnais de rendu Chromium — GL-19 (vague 1, file D).
 *
 * Monte les VRAIES fenetres de dialogue du Studio, avec leurs vrais imports,
 * pour verifier dans un navigateur que le bandeau « vous echangez avec une
 * IA » est present au premier contact — c'est-a-dire avant tout message.
 *
 * Ce n'est pas une page de l'application : elle n'est pas routee et n'est pas
 * construite par `npm run build` (point d'entree distinct). Les appels reseau
 * des composants sont neutralises ici, parce que ce qui est teste est le
 * rendu, pas le transport.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { LangProvider } from '../../src/contexts/LangContext';
import ChatSidebarStudio from '../../src/components/studio/ChatSidebarStudio';
import ChatSidebar from '../../src/components/ChatSidebar';
import AiDisclosureBanner from '../../src/components/AiDisclosureBanner';
import '../../src/index.css';

// Aucun backend ici : toute requete rend une reponse vide, comme une fenetre
// ouverte sur une execution qui n'a encore rien produit.
window.fetch = (async () =>
  new Response(JSON.stringify({ agents: [], messages: [] }), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })) as typeof fetch;

const quelle = new URLSearchParams(window.location.search).get('vue') ?? 'studio';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LangProvider>
      {quelle === 'studio' && (
        <ChatSidebarStudio executionId={1} isOpen onClose={() => {}} />
      )}
      {quelle === 'legacy' && <ChatSidebar executionId={1} isOpen onClose={() => {}} />}
      {quelle === 'banner' && <AiDisclosureBanner />}
    </LangProvider>
  </StrictMode>,
);
