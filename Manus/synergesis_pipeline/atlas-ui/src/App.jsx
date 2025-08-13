import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import KnowledgeGraph from './components/KnowledgeGraph';
import SystemDashboard from './components/SystemDashboard';
import { 
  Brain, Database, Activity, Settings, Plus, RefreshCw,
  Search, Filter, Download, Upload
} from 'lucide-react';
import './App.css';

function App() {
  const [concepts, setConcepts] = useState([]);
  const [systemMetrics, setSystemMetrics] = useState(null);
  const [healthReport, setHealthReport] = useState(null);
  const [selectedConcept, setSelectedConcept] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  // Données de démonstration
  const demoData = {
    concepts: [
      {
        concept_id: "concept_ai_001",
        natural_prompt: "Intelligence artificielle et apprentissage automatique",
        concept_type: "TECHNICAL_CONCEPT",
        source: "AI_Research_Papers",
        resonance: 0.8,
        weight: 0.9,
        timestamp: Date.now()
      },
      {
        concept_id: "concept_quantum_002",
        natural_prompt: "Mécanique quantique et intrication",
        concept_type: "SCIENTIFIC_CONCEPT",
        source: "Physics_Textbook",
        resonance: 0.7,
        weight: 0.8,
        timestamp: Date.now()
      },
      {
        concept_id: "concept_ethics_003",
        natural_prompt: "Éthique de l'intelligence artificielle",
        concept_type: "PHILOSOPHICAL_CONCEPT",
        source: "Ethics_Journal",
        resonance: 0.6,
        weight: 0.7,
        timestamp: Date.now()
      },
      {
        concept_id: "concept_business_004",
        natural_prompt: "Transformation digitale des entreprises",
        concept_type: "BUSINESS_CONCEPT",
        source: "Business_Report",
        resonance: 0.5,
        weight: 0.6,
        timestamp: Date.now()
      },
      {
        concept_id: "concept_neural_005",
        natural_prompt: "Réseaux de neurones convolutionnels",
        concept_type: "TECHNICAL_CONCEPT",
        source: "Deep_Learning_Book",
        resonance: 0.9,
        weight: 0.8,
        timestamp: Date.now()
      }
    ],
    systemMetrics: {
      total_concepts: 5,
      knowledge_gaps: 2,
      logical_inconsistencies: 1,
      pending_suggestions: 3,
      applied_suggestions: 7,
      average_resonance: 0.7,
      average_weight: 0.76,
      concept_types_distribution: {
        "TECHNICAL_CONCEPT": 2,
        "SCIENTIFIC_CONCEPT": 1,
        "PHILOSOPHICAL_CONCEPT": 1,
        "BUSINESS_CONCEPT": 1
      }
    },
    healthReport: {
      overall_status: 'healthy',
      trends: {
        total_concepts: 'increasing',
        knowledge_gaps: 'stable',
        logical_inconsistencies: 'decreasing',
        pending_suggestions: 'increasing'
      },
      anomalies: [],
      recommendations: [
        "Considérer l'ajout de plus de concepts scientifiques pour équilibrer la base de connaissances",
        "Surveiller l'augmentation des suggestions en attente"
      ]
    }
  };

  // Simulation de la connexion à l'API NOUS
  const connectToNous = async () => {
    setIsLoading(true);
    try {
      // Simuler un appel API
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Pour la démo, utiliser les données simulées
      setConcepts(demoData.concepts);
      setSystemMetrics(demoData.systemMetrics);
      setHealthReport(demoData.healthReport);
      setConnectionStatus('connected');
    } catch (error) {
      console.error('Erreur de connexion à NOUS:', error);
      setConnectionStatus('error');
    } finally {
      setIsLoading(false);
    }
  };

  // Rafraîchir les données
  const refreshData = async () => {
    if (connectionStatus === 'connected') {
      await connectToNous();
    }
  };

  // Gestionnaire de sélection de concept
  const handleConceptSelect = (concept) => {
    setSelectedConcept(concept);
  };

  // Charger les données au démarrage
  useEffect(() => {
    connectToNous();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Atlas</h1>
              <p className="text-sm text-gray-600">Visualisation des Connaissances Synergesis</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <Badge 
              variant={connectionStatus === 'connected' ? 'default' : 'destructive'}
              className="flex items-center gap-1"
            >
              <div className={`w-2 h-2 rounded-full ${
                connectionStatus === 'connected' ? 'bg-green-500' : 'bg-red-500'
              }`} />
              {connectionStatus === 'connected' ? 'Connecté' : 'Déconnecté'}
            </Badge>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={refreshData}
              disabled={isLoading}
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Actualiser
            </Button>
            
            <Button size="sm">
              <Plus className="w-4 h-4 mr-2" />
              Nouveau Concept
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6">
        <Tabs defaultValue="graph" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="graph" className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              Graphe
            </TabsTrigger>
            <TabsTrigger value="dashboard" className="flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Tableau de Bord
            </TabsTrigger>
            <TabsTrigger value="concepts" className="flex items-center gap-2">
              <Search className="w-4 h-4" />
              Concepts
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center gap-2">
              <Settings className="w-4 h-4" />
              Paramètres
            </TabsTrigger>
          </TabsList>

          {/* Onglet Graphe */}
          <TabsContent value="graph" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <KnowledgeGraph 
                  concepts={concepts}
                  onConceptSelect={handleConceptSelect}
                />
              </div>
              
              <div className="space-y-4">
                {selectedConcept ? (
                  <Card>
                    <CardHeader>
                      <CardTitle>Détails du Concept</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div>
                        <label className="text-sm font-medium text-gray-600">ID</label>
                        <p className="text-sm">{selectedConcept.concept_id}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Description</label>
                        <p className="text-sm">{selectedConcept.natural_prompt}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Type</label>
                        <Badge variant="secondary">{selectedConcept.concept_type}</Badge>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Source</label>
                        <p className="text-sm">{selectedConcept.source}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-sm font-medium text-gray-600">Résonance</label>
                          <p className="text-sm font-semibold">{(selectedConcept.resonance * 100).toFixed(0)}%</p>
                        </div>
                        <div>
                          <label className="text-sm font-medium text-gray-600">Poids</label>
                          <p className="text-sm font-semibold">{(selectedConcept.weight * 100).toFixed(0)}%</p>
                        </div>
                      </div>
                      <div className="pt-3 border-t">
                        <Button size="sm" className="w-full">
                          Modifier
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <Card>
                    <CardContent className="p-6 text-center text-gray-500">
                      <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>Sélectionnez un concept dans le graphe pour voir ses détails</p>
                    </CardContent>
                  </Card>
                )}
                
                <Card>
                  <CardHeader>
                    <CardTitle>Actions Rapides</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <Button variant="outline" size="sm" className="w-full justify-start">
                      <Upload className="w-4 h-4 mr-2" />
                      Importer des Concepts
                    </Button>
                    <Button variant="outline" size="sm" className="w-full justify-start">
                      <Download className="w-4 h-4 mr-2" />
                      Exporter le Graphe
                    </Button>
                    <Button variant="outline" size="sm" className="w-full justify-start">
                      <Filter className="w-4 h-4 mr-2" />
                      Filtres Avancés
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Onglet Tableau de Bord */}
          <TabsContent value="dashboard">
            <SystemDashboard 
              systemMetrics={systemMetrics}
              healthReport={healthReport}
            />
          </TabsContent>

          {/* Onglet Concepts */}
          <TabsContent value="concepts">
            <Card>
              <CardHeader>
                <CardTitle>Liste des Concepts</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {concepts.map((concept, index) => (
                    <div 
                      key={concept.concept_id || index}
                      className="p-4 border rounded-lg hover:bg-gray-50 cursor-pointer"
                      onClick={() => handleConceptSelect(concept)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-medium">{concept.concept_id}</h3>
                          <p className="text-sm text-gray-600 mt-1">{concept.natural_prompt}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <Badge variant="secondary" className="text-xs">
                              {concept.concept_type}
                            </Badge>
                            <span className="text-xs text-gray-500">
                              Résonance: {(concept.resonance * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                        <Button variant="ghost" size="sm">
                          Modifier
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Onglet Paramètres */}
          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle>Paramètres de Configuration</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div>
                    <h3 className="font-medium mb-3">Connexion API NOUS</h3>
                    <div className="space-y-2">
                      <div>
                        <label className="text-sm font-medium">URL de l'API</label>
                        <input 
                          type="text" 
                          defaultValue="http://localhost:8001"
                          className="w-full mt-1 px-3 py-2 border rounded-md"
                        />
                      </div>
                      <div>
                        <label className="text-sm font-medium">Token d'authentification</label>
                        <input 
                          type="password" 
                          defaultValue="synergesis_nous_token_2025"
                          className="w-full mt-1 px-3 py-2 border rounded-md"
                        />
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="font-medium mb-3">Visualisation</h3>
                    <div className="space-y-2">
                      <label className="flex items-center gap-2">
                        <input type="checkbox" defaultChecked />
                        <span className="text-sm">Afficher les relations automatiques</span>
                      </label>
                      <label className="flex items-center gap-2">
                        <input type="checkbox" defaultChecked />
                        <span className="text-sm">Animation des transitions</span>
                      </label>
                      <label className="flex items-center gap-2">
                        <input type="checkbox" />
                        <span className="text-sm">Mode sombre</span>
                      </label>
                    </div>
                  </div>
                  
                  <div className="pt-4 border-t">
                    <Button>Sauvegarder les Paramètres</Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

export default App;
