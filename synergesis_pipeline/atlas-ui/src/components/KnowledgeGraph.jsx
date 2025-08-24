import React, { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Search, Filter, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import './App.css';

const KnowledgeGraph = ({ concepts = [], onConceptSelect }) => {
  const svgRef = useRef(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedConceptType, setSelectedConceptType] = useState('all');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Filtrer les concepts
  const filteredConcepts = concepts.filter(concept => {
    const matchesSearch = concept.natural_prompt?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         concept.concept_id?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = selectedConceptType === 'all' || concept.concept_type === selectedConceptType;
    return matchesSearch && matchesType;
  });

  // Obtenir les types de concepts uniques
  const conceptTypes = ['all', ...new Set(concepts.map(c => c.concept_type).filter(Boolean))];

  // Générer les positions des nœuds (disposition en cercle pour la démo)
  const generateNodePositions = (concepts) => {
    const centerX = 400;
    const centerY = 300;
    const radius = 200;
    
    return concepts.map((concept, index) => {
      const angle = (index / concepts.length) * 2 * Math.PI;
      return {
        ...concept,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      };
    });
  };

  const nodesWithPositions = generateNodePositions(filteredConcepts);

  // Générer des liens basés sur la similarité des types
  const generateLinks = (nodes) => {
    const links = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        if (nodes[i].concept_type === nodes[j].concept_type && Math.random() > 0.7) {
          links.push({
            source: i,
            target: j,
            strength: Math.random()
          });
        }
      }
    }
    return links;
  };

  const links = generateLinks(nodesWithPositions);

  // Gestionnaires d'événements pour le zoom et le pan
  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(prev => Math.max(0.1, Math.min(3, prev * delta)));
  };

  const handleMouseDown = (e) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Couleurs pour les différents types de concepts
  const getNodeColor = (conceptType) => {
    const colors = {
      'TECHNICAL_CONCEPT': '#3b82f6',
      'BUSINESS_CONCEPT': '#10b981',
      'SCIENTIFIC_CONCEPT': '#8b5cf6',
      'PHILOSOPHICAL_CONCEPT': '#f59e0b',
      'default': '#6b7280'
    };
    return colors[conceptType] || colors.default;
  };

  // Taille du nœud basée sur la résonance
  const getNodeSize = (resonance) => {
    const baseSize = 8;
    const maxSize = 20;
    if (!resonance) return baseSize;
    return baseSize + (resonance * (maxSize - baseSize));
  };

  useEffect(() => {
    const svg = svgRef.current;
    if (svg) {
      svg.addEventListener('wheel', handleWheel);
      svg.addEventListener('mousedown', handleMouseDown);
      svg.addEventListener('mousemove', handleMouseMove);
      svg.addEventListener('mouseup', handleMouseUp);
      svg.addEventListener('mouseleave', handleMouseUp);

      return () => {
        svg.removeEventListener('wheel', handleWheel);
        svg.removeEventListener('mousedown', handleMouseDown);
        svg.removeEventListener('mousemove', handleMouseMove);
        svg.removeEventListener('mouseup', handleMouseUp);
        svg.removeEventListener('mouseleave', handleMouseUp);
      };
    }
  }, [isDragging, dragStart, pan]);

  return (
    <Card className="w-full h-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Graphe de Connaissances</span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={resetView}>
              <RotateCcw className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={() => setZoom(prev => Math.min(3, prev * 1.2))}>
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={() => setZoom(prev => Math.max(0.1, prev * 0.8))}>
              <ZoomOut className="w-4 h-4" />
            </Button>
          </div>
        </CardTitle>
        <div className="flex gap-4 items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              placeholder="Rechercher des concepts..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          <select
            value={selectedConceptType}
            onChange={(e) => setSelectedConceptType(e.target.value)}
            className="px-3 py-2 border rounded-md bg-background"
          >
            {conceptTypes.map(type => (
              <option key={type} value={type}>
                {type === 'all' ? 'Tous les types' : type}
              </option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="relative w-full h-96 overflow-hidden border rounded-lg">
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            className="cursor-move"
            style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
          >
            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* Liens */}
              {links.map((link, index) => {
                const sourceNode = nodesWithPositions[link.source];
                const targetNode = nodesWithPositions[link.target];
                if (!sourceNode || !targetNode) return null;
                
                return (
                  <line
                    key={index}
                    x1={sourceNode.x}
                    y1={sourceNode.y}
                    x2={targetNode.x}
                    y2={targetNode.y}
                    stroke="#e5e7eb"
                    strokeWidth={link.strength * 2}
                    opacity={0.6}
                  />
                );
              })}
              
              {/* Nœuds */}
              {nodesWithPositions.map((node, index) => (
                <g key={node.concept_id || index}>
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={getNodeSize(node.resonance)}
                    fill={getNodeColor(node.concept_type)}
                    stroke="#fff"
                    strokeWidth="2"
                    className="cursor-pointer hover:opacity-80 transition-opacity"
                    onClick={() => onConceptSelect && onConceptSelect(node)}
                  />
                  <text
                    x={node.x}
                    y={node.y + getNodeSize(node.resonance) + 15}
                    textAnchor="middle"
                    fontSize="10"
                    fill="#374151"
                    className="pointer-events-none"
                  >
                    {node.concept_id?.substring(0, 15) || 'Concept'}
                    {node.concept_id?.length > 15 ? '...' : ''}
                  </text>
                </g>
              ))}
            </g>
          </svg>
          
          {/* Légende */}
          <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm p-3 rounded-lg shadow-lg">
            <h4 className="font-semibold text-sm mb-2">Légende</h4>
            <div className="space-y-1 text-xs">
              {conceptTypes.slice(1).map(type => (
                <div key={type} className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: getNodeColor(type) }}
                  />
                  <span>{type}</span>
                </div>
              ))}
            </div>
            <div className="mt-2 pt-2 border-t">
              <div className="text-xs text-gray-600">
                Taille = Résonance
              </div>
            </div>
          </div>
          
          {/* Informations de zoom */}
          <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm px-2 py-1 rounded text-xs">
            Zoom: {(zoom * 100).toFixed(0)}%
          </div>
        </div>
        
        {/* Statistiques */}
        <div className="p-4 border-t">
          <div className="flex gap-4 text-sm">
            <Badge variant="secondary">
              {filteredConcepts.length} concepts affichés
            </Badge>
            <Badge variant="secondary">
              {links.length} relations
            </Badge>
            {searchTerm && (
              <Badge variant="outline">
                Filtré par: "{searchTerm}"
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default KnowledgeGraph;

