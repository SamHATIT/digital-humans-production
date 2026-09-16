/**
 * StudioChatPage — dialogue authentifié hors projet (BILL-06).
 *
 * Le palier Free vend un dialogue avec Sophie et Olivia, mais ne peut créer
 * aucun projet (`max_projects: 0`) : les deux autres fenêtres de dialogue du
 * Studio exigent un projet ou une exécution. Cette page parle à
 * `POST /api/studio/chat`, qui n'exige ni l'un ni l'autre.
 *
 * La liste des interlocuteurs vient du serveur (`GET /api/studio/chat/agents`)
 * plutôt que d'une constante : afficher un agent que le backend refusera en
 * 403 est exactement le défaut corrigé par le lot 3 de la vague 2.
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Send } from 'lucide-react';
import { api } from '../services/api';
import { useLang } from '../contexts/LangContext';
import AiDisclosureBanner from '../components/AiDisclosureBanner';
import { renderInlineMarkdown } from '../lib/safeMarkdown';

interface StudioAgentRow {
  agent_id: string;
  name: string;
  role: string;
  available: boolean;
  required_feature: string;
}

interface Turn {
  role: 'user' | 'assistant';
  content: string;
}

const MD_CLASSES = {
  code: 'px-1 py-0.5 bg-ink-3 text-brass-2 text-[11px] font-mono',
  strong: 'text-bone font-semibold',
  em: 'text-bone-2',
};

export default function StudioChatPage() {
  const { t } = useLang();

  const [agents, setAgents] = useState<StudioAgentRow[]>([]);
  const [tier, setTier] = useState<string>('');
  const [agentId, setAgentId] = useState('sophie');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .get('/api/studio/chat/agents')
      .then((data: any) => {
        setAgents(data?.agents ?? []);
        setTier(data?.tier ?? '');
      })
      .catch((err: unknown) => {
        // Règle 6 : une liste vide serait indistinguable d'un compte sans
        // aucun interlocuteur. On dit que le chargement a échoué.
        setError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  const send = async () => {
    const message = input.trim();
    if (!message || sending) return;
    setInput('');
    setError(null);
    const historique = turns;
    setTurns((prev) => [...prev, { role: 'user', content: message }]);
    setSending(true);
    try {
      const data = await api.post('/api/studio/chat', {
        message,
        agent_id: agentId,
        history: historique,
      });
      setTurns((prev) => [...prev, { role: 'assistant', content: data.response }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
    }
  };

  const joignables = agents.filter((a) => a.available);
  const fermes = agents.filter((a) => !a.available);
  const courant = agents.find((a) => a.agent_id === agentId);

  return (
    <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <header className="mb-8">
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
          № 01 · {t('The conversation', "L'entretien")}
          {tier && <span className="ml-2 text-bone-4">· {tier}</span>}
        </p>
        <h1 className="mt-3 font-serif italic text-4xl text-bone leading-tight">
          {t('Talk it through first.', "Parlons-en d'abord.")}
        </h1>
        <p className="mt-3 max-w-2xl font-mono text-[12px] leading-relaxed text-bone-3">
          {t(
            'Describe what you need. Sophie frames the project, Olivia turns it into requirements. No project to create, nothing to set up.',
            "Décrivez votre besoin. Sophie cadre le projet, Olivia le traduit en exigences. Aucun projet à créer, rien à configurer.",
          )}
        </p>
      </header>

      {/* Choix de l'interlocuteur — servi par le backend, pas devine ici. */}
      <div className="mb-6 flex flex-wrap items-center gap-2">
        {joignables.map((agent) => (
          <button
            key={agent.agent_id}
            type="button"
            onClick={() => setAgentId(agent.agent_id)}
            className={[
              'px-4 py-2 border font-mono text-[10px] tracking-eyebrow uppercase transition-colors',
              agent.agent_id === agentId
                ? 'border-brass text-brass'
                : 'border-bone/15 text-bone-3 hover:text-bone hover:border-bone/30',
            ].join(' ')}
          >
            {agent.name} · {agent.role}
          </button>
        ))}
        {fermes.length > 0 && (
          <Link
            to="/pricing"
            className="px-4 py-2 border border-bone/10 font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 hover:text-brass hover:border-brass/40 transition-colors"
          >
            {t(
              `+ ${fermes.length} with a paid plan`,
              `+ ${fermes.length} avec un abonnement`,
            )}
          </Link>
        )}
      </div>

      <div className="bg-ink-2 border border-bone/10">
        <AiDisclosureBanner />

        <div className="min-h-[320px] max-h-[520px] overflow-y-auto p-5 space-y-4">
          {turns.length === 0 ? (
            <p className="py-16 text-center font-serif italic text-bone-3">
              {t(
                `Say hello to ${courant?.name ?? 'Sophie'}.`,
                `Dites bonjour à ${courant?.name ?? 'Sophie'}.`,
              )}
            </p>
          ) : (
            turns.map((turn, idx) => (
              <div
                key={idx}
                className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] px-4 py-3 border ${
                    turn.role === 'user'
                      ? 'bg-brass/10 border-brass/30 text-bone'
                      : 'bg-ink-3 border-bone/10 text-bone-2'
                  }`}
                >
                  <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-1.5">
                    {turn.role === 'user' ? t('You', 'Vous') : (courant?.name ?? 'Sophie')}
                  </p>
                  <p className="font-serif text-[14px] leading-relaxed whitespace-pre-wrap break-words">
                    {renderInlineMarkdown(turn.content, MD_CLASSES)}
                  </p>
                </div>
              </div>
            ))
          )}
          {sending && (
            <p className="flex items-center gap-2 font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-brass" />
              {t('Thinking…', 'Réflexion…')}
            </p>
          )}
          <div ref={endRef} />
        </div>

        {error && (
          <p className="border-t border-error/30 bg-error/5 px-5 py-3 font-mono text-[11px] text-error">
            {error}
          </p>
        )}

        <div className="border-t border-bone/10 p-5 flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            rows={2}
            placeholder={t('Describe your project…', 'Décrivez votre projet…')}
            className="flex-1 bg-ink-3 border border-bone/10 px-4 py-3 font-serif text-[14px] text-bone placeholder:text-bone-4 focus:border-brass focus:outline-none resize-none"
          />
          <button
            type="button"
            onClick={() => void send()}
            disabled={!input.trim() || sending}
            className="inline-flex items-center gap-2 px-4 py-3 bg-brass text-ink font-mono text-[10px] tracking-cta uppercase hover:bg-brass-2 transition-colors disabled:opacity-50"
          >
            {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            {t('Send', 'Envoyer')}
          </button>
        </div>
      </div>

      <p className="mt-4 font-mono text-[10px] text-bone-4">
        {t(
          'This conversation is not stored: it lives in this tab only.',
          "Cette conversation n'est pas conservée : elle ne vit que dans cet onglet.",
        )}
      </p>
    </section>
  );
}
