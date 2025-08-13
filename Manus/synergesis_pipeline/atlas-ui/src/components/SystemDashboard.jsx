import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Area, AreaChart
} from 'recharts';
import { 
  Brain, AlertTriangle, CheckCircle, Clock, TrendingUp, TrendingDown,
  Activity, Database, Zap, Target
} from 'lucide-react';
import './App.css';

const SystemDashboard = ({ systemMetrics, healthReport }) => {
  // Données par défaut si aucune métrique n'est fournie
  const defaultMetrics = {
    total_concepts: 0,
    knowledge_gaps: 0,
    logical_inconsistencies: 0,
    pending_suggestions: 0,
    applied_suggestions: 0,
    average_resonance: 0,
    average_weight: 0,
    concept_types_distribution: {}
  };

  const metrics = systemMetrics || defaultMetrics;
  const health = healthReport || { overall_status: 'unknown', trends: {}, anomalies: [], recommendations: [] };

  // Données pour les graphiques
  const conceptTypesData = Object.entries(metrics.concept_types_distribution || {}).map(([type, count]) => ({
    name: type,
    value: count
  }));

  const trendsData = [
    { name: 'Concepts', value: metrics.total_concepts, trend: health.trends?.total_concepts || 'stable' },
    { name: 'Lacunes', value: metrics.knowledge_gaps, trend: health.trends?.knowledge_gaps || 'stable' },
    { name: 'Incohérences', value: metrics.logical_inconsistencies, trend: health.trends?.logical_inconsistencies || 'stable' },
    { name: 'Suggestions', value: metrics.pending_suggestions, trend: health.trends?.pending_suggestions || 'stable' }
  ];

  const qualityMetrics = [
    { name: 'Résonance Moy.', value: metrics.average_resonance, max: 1 },
    { name: 'Poids Moyen', value: metrics.average_weight, max: 1 }
  ];

  // Couleurs pour les graphiques
  const COLORS = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#6b7280'];

  // Statut de santé
  const getHealthStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-green-600 bg-green-100';
      case 'warning': return 'text-yellow-600 bg-yellow-100';
      case 'critical': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getHealthStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="w-5 h-5" />;
      case 'warning': return <AlertTriangle className="w-5 h-5" />;
      case 'critical': return <AlertTriangle className="w-5 h-5" />;
      default: return <Activity className="w-5 h-5" />;
    }
  };

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'increasing': return <TrendingUp className="w-4 h-4 text-green-600" />;
      case 'decreasing': return <TrendingDown className="w-4 h-4 text-red-600" />;
      default: return <Activity className="w-4 h-4 text-gray-600" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Statut de santé global */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="w-6 h-6" />
            Statut de Santé du Système
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${getHealthStatusColor(health.overall_status)}`}>
              {getHealthStatusIcon(health.overall_status)}
              <span className="font-semibold capitalize">{health.overall_status}</span>
            </div>
            <div className="text-sm text-gray-600">
              Dernière mise à jour: {new Date().toLocaleTimeString()}
            </div>
          </div>
          
          {health.anomalies && health.anomalies.length > 0 && (
            <div className="mt-4">
              <h4 className="font-semibold text-sm mb-2 text-red-600">Anomalies Détectées</h4>
              <div className="space-y-1">
                {health.anomalies.map((anomaly, index) => (
                  <div key={index} className="text-sm bg-red-50 text-red-700 px-3 py-2 rounded">
                    {anomaly}
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Métriques principales */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {trendsData.map((item, index) => (
          <Card key={item.name}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">{item.name}</p>
                  <p className="text-2xl font-bold">{item.value}</p>
                </div>
                <div className="flex items-center gap-1">
                  {getTrendIcon(item.trend)}
                  <span className="text-xs text-gray-500 capitalize">{item.trend}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Graphiques */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Distribution des types de concepts */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5" />
              Distribution des Types de Concepts
            </CardTitle>
          </CardHeader>
          <CardContent>
            {conceptTypesData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={conceptTypesData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {conceptTypesData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-300 flex items-center justify-center text-gray-500">
                Aucune donnée disponible
              </div>
            )}
          </CardContent>
        </Card>

        {/* Métriques de qualité */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5" />
              Métriques de Qualité
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {qualityMetrics.map((metric, index) => (
                <div key={metric.name}>
                  <div className="flex justify-between text-sm mb-2">
                    <span>{metric.name}</span>
                    <span>{(metric.value * 100).toFixed(1)}%</span>
                  </div>
                  <Progress value={(metric.value / metric.max) * 100} className="h-2" />
                </div>
              ))}
              
              <div className="pt-4 border-t">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-gray-600">Suggestions Appliquées</div>
                    <div className="text-lg font-semibold">{metrics.applied_suggestions}</div>
                  </div>
                  <div>
                    <div className="text-gray-600">En Attente</div>
                    <div className="text-lg font-semibold">{metrics.pending_suggestions}</div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recommandations */}
      {health.recommendations && health.recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Recommandations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {health.recommendations.map((recommendation, index) => (
                <div key={index} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0" />
                  <div className="text-sm text-blue-800">{recommendation}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Activité récente */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Activité Récente
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-3 border rounded-lg">
              <div className="w-2 h-2 bg-green-500 rounded-full" />
              <div className="flex-1">
                <div className="text-sm font-medium">Collecte de métriques</div>
                <div className="text-xs text-gray-600">Il y a 5 minutes</div>
              </div>
              <Badge variant="secondary">Automatique</Badge>
            </div>
            
            <div className="flex items-center gap-3 p-3 border rounded-lg">
              <div className="w-2 h-2 bg-blue-500 rounded-full" />
              <div className="flex-1">
                <div className="text-sm font-medium">Analyse des tendances</div>
                <div className="text-xs text-gray-600">Il y a 15 minutes</div>
              </div>
              <Badge variant="secondary">Chronos</Badge>
            </div>
            
            <div className="flex items-center gap-3 p-3 border rounded-lg">
              <div className="w-2 h-2 bg-purple-500 rounded-full" />
              <div className="flex-1">
                <div className="text-sm font-medium">Génération de rapport de santé</div>
                <div className="text-xs text-gray-600">Il y a 1 heure</div>
              </div>
              <Badge variant="secondary">Système</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SystemDashboard;

