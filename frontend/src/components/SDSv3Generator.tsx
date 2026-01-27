import React, { useState } from 'react';
import { executions } from '../services/api';

interface SDSv3GeneratorProps {
  executionId: number;
  projectName: string;
  onComplete?: () => void;
}

interface GenerationResult {
  status: string;
  pipeline_summary: {
    use_cases_processed: number;
    requirement_sheets: number;
    domains_generated: number;
    domains: string[];
  };
  costs: {
    synthesis_cost_usd: number;
    total_tokens: number;
  };
  timing: {
    total_time_seconds: number;
  };
  output: {
    download_url: string;
  };
}

export default function SDSv3Generator({ executionId, projectName, onComplete }: SDSv3GeneratorProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>('');

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    setProgress('Initialisation du pipeline SDS v3...');

    try {
      setProgress('Analyse des Use Cases en cours...');
      const response = await executions.generateSDSv3(executionId);
      
      setResult(response);
      setProgress('');
      
      if (onComplete) {
        onComplete();
      }
    } catch (err: any) {
      console.error('SDS v3 generation error:', err);
      setError(err.message || 'Erreur lors de la génération du SDS');
      setProgress('');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = () => {
    const downloadUrl = executions.downloadSDSv3(executionId);
    window.open(downloadUrl, '_blank');
  };

  return (
    <div className="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-lg p-6 text-white">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <div>
          <h3 className="font-bold text-lg">SDS v3 Generator</h3>
          <p className="text-blue-200 text-sm">Pipeline optimisé avec micro-analyse</p>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-800/50 rounded-lg p-4 mb-4">
        <p className="text-sm text-blue-100">
          Le pipeline SDS v3 utilise une approche en micro-analyse pour réduire les coûts de 99% 
          tout en maintenant une qualité professionnelle. Coût estimé : ~$0.10 pour 10 UCs.
        </p>
      </div>

      {/* Generate Button */}
      {!result && (
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className={`w-full py-3 px-4 rounded-lg font-medium transition-all ${
            isGenerating
              ? 'bg-blue-700 cursor-not-allowed'
              : 'bg-blue-500 hover:bg-blue-400'
          }`}
        >
          {isGenerating ? (
            <div className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Génération en cours...</span>
            </div>
          ) : (
            '🚀 Générer SDS v3 (DOCX)'
          )}
        </button>
      )}

      {/* Progress */}
      {progress && (
        <div className="mt-4 p-3 bg-blue-800/50 rounded-lg">
          <p className="text-blue-100 text-sm animate-pulse">{progress}</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 p-3 bg-red-900/50 border border-red-500 rounded-lg">
          <p className="text-red-200 text-sm">{error}</p>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="mt-4 space-y-4">
          {/* Success Badge */}
          <div className="flex items-center gap-2 text-green-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="font-medium">SDS généré avec succès !</span>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-blue-800/50 rounded p-3">
              <p className="text-blue-300 text-xs uppercase">Use Cases</p>
              <p className="text-xl font-bold">{result.pipeline_summary.use_cases_processed}</p>
            </div>
            <div className="bg-blue-800/50 rounded p-3">
              <p className="text-blue-300 text-xs uppercase">Domaines</p>
              <p className="text-xl font-bold">{result.pipeline_summary.domains_generated}</p>
            </div>
            <div className="bg-blue-800/50 rounded p-3">
              <p className="text-blue-300 text-xs uppercase">Coût</p>
              <p className="text-xl font-bold">${result.costs.synthesis_cost_usd.toFixed(4)}</p>
            </div>
            <div className="bg-blue-800/50 rounded p-3">
              <p className="text-blue-300 text-xs uppercase">Temps</p>
              <p className="text-xl font-bold">{result.timing.total_time_seconds}s</p>
            </div>
          </div>

          {/* Domains List */}
          <div className="bg-blue-800/50 rounded p-3">
            <p className="text-blue-300 text-xs uppercase mb-2">Domaines fonctionnels</p>
            <div className="flex flex-wrap gap-2">
              {result.pipeline_summary.domains.map((domain, index) => (
                <span key={index} className="px-2 py-1 bg-blue-600/50 rounded text-sm">
                  {domain}
                </span>
              ))}
            </div>
          </div>

          {/* Download Button */}
          <button
            onClick={handleDownload}
            className="w-full py-3 px-4 bg-green-600 hover:bg-green-500 rounded-lg font-medium flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Télécharger le SDS ({projectName}.docx)
          </button>
        </div>
      )}
    </div>
  );
}
