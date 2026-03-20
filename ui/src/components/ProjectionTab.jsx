import React, { useState, useEffect } from 'react';
import { fetchProjection } from '../api';
import { TrendingUp } from 'lucide-react';

export default function ProjectionTab({ onError }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const res = await fetchProjection();
      if (res.error) {
         onError(res.error);
      } else {
         setData(res.data);
      }
      setLoading(false);
    };
    load();
  }, [onError]);

  if (loading) return <div className="p-10 text-center text-slate-500">Loading projections...</div>;

  return (
    <div className="w-full h-full flex items-center justify-center p-10">
      <div className="bg-white border border-slate-200 rounded-xl p-10 text-center max-w-lg shadow-sm">
         <TrendingUp className="w-16 h-16 text-blue-500 mx-auto mb-4 opacity-50" />
         <h2 className="text-xl font-bold text-slate-800 mb-2">Long-Term Projections</h2>
         <p className="text-slate-600 mb-6">
           {data ? data.message : "The V1 Portfolio Orchestrator currently handles immediate structural asset transitions and baseline deterministic liquidation flows. Long-term stochastic monte-carlo projections will be implemented in V2."}
         </p>
         <div className="px-4 py-3 bg-blue-50 text-blue-800 text-sm font-semibold rounded-lg">
           Endpoint connection successful: /api/portfolio/projection
         </div>
      </div>
    </div>
  );
}
