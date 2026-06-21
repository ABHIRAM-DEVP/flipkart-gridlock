"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

function heatColor(t: number) {
  const v = Math.max(0, Math.min(1, t));
  return `rgb(${Math.floor(255 * v)},${Math.floor(200 * (1 - v))},0)`;
}

function impactColor(v: number) {
  if (v > 0.75) return "red";
  if (v > 0.4) return "orange";
  return "green";
}

function resourceIcon(type: string) {
  return L.icon({
    iconUrl:
      type === "personnel"
        ? "/icons/person.svg"
        : "/icons/marker.svg",
    iconSize: [28, 28],
    iconAnchor: [14, 28],
  });
}

export const HotspotsMap = ({
  hotspots: inputHotspots = [],
}: {
  hotspots?: any[];
}) => {
  const [events, setEvents] = useState<any[]>([]);
  const [resources, setResources] = useState<any[]>([]);

  const mapRef = useRef<any>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  const hotspotLayerRef = useRef<any>(null);
  const eventLayerRef = useRef<any>(null);
  const resourceLayerRef = useRef<any>(null);

  const normalized = useMemo(() => {
    return inputHotspots
      .map((h) => ({
        ...h,
        lat: Number(h.centroid_latitude ?? h.latitude ?? h.lat),
        lng: Number(h.centroid_longitude ?? h.longitude ?? h.lng),
        score: Number(h.hotspot_score ?? h.score ?? 0),
        count: Number(h.count ?? h.cluster_size ?? 0),
        duration: Number(
          h.avg_duration_min ?? h.avg_duration ?? 0
        ),
      }))
      .filter(
        (h) =>
          Number.isFinite(h.lat) &&
          Number.isFinite(h.lng)
      );
  }, [inputHotspots]);

  const lats = normalized.map((h) => h.lat);
  const lngs = normalized.map((h) => h.lng);

  const centerLat =
    lats.length > 0
      ? (Math.min(...lats) + Math.max(...lats)) / 2
      : 28.7041;

  const centerLng =
    lngs.length > 0
      ? (Math.min(...lngs) + Math.max(...lngs)) / 2
      : 77.1025;

  const maxScore = Math.max(
    ...normalized.map((h) => h.score),
    1
  );

  useEffect(() => {
    async function loadData() {
      try {
        const res = await fetch("/api/events");
        const data = await res.json();
        setEvents(data.events || []);
      } catch {}

      try {
        const res = await fetch("/api/resources");
        const data = await res.json();
        setResources(data.resources || []);
      } catch {}
    }

    loadData();

    if (!mapContainerRef.current || mapRef.current)
      return;

    const map = L.map(mapContainerRef.current)
      .setView([centerLat, centerLng], 12);

    mapRef.current = map;

    const baseLayer = L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        attribution: "© OpenStreetMap contributors",
      }
    );

    baseLayer.addTo(map);

    hotspotLayerRef.current =
      L.layerGroup().addTo(map);

    eventLayerRef.current =
      L.layerGroup().addTo(map);

    resourceLayerRef.current =
      L.layerGroup().addTo(map);

    L.control.layers(
      { OpenStreetMap: baseLayer },
      {
        Hotspots: hotspotLayerRef.current,
        Events: eventLayerRef.current,
        Resources: resourceLayerRef.current,
      }
    ).addTo(map);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const layer = hotspotLayerRef.current;
    if (!layer) return;

    layer.clearLayers();

    normalized.forEach((h) => {
      L.circleMarker([h.lat, h.lng], {
        radius: 6 + (h.score / maxScore) * 18,
        color: heatColor(h.score / maxScore),
        fillOpacity: 0.6,
      })
        .bindPopup(
          `<strong>${h.count} events</strong>`
        )
        .addTo(layer);
    });
  }, [normalized, maxScore]);

  return (
    <div
      ref={mapContainerRef}
      className="h-[500px] w-full rounded-2xl overflow-hidden"
    />
  );
};