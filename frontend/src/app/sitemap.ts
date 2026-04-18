import type { MetadataRoute } from "next";
import { ANNONCES } from "@/data/annonces";
import { CAS_LIST } from "@/data/cas-usage";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://finsight-ia.com";
  const now = new Date();

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${base}/`, lastModified: now, changeFrequency: "weekly", priority: 1.0 },
    { url: `${base}/app`, lastModified: now, changeFrequency: "daily", priority: 0.95 },
    { url: `${base}/analyste`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: `${base}/collaboration`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${base}/cas-usage`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${base}/methodologie`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${base}/securite`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${base}/comparatif`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${base}/about`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/contact`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/mentions-legales`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/cgu`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/disclaimer`, lastModified: now, changeFrequency: "yearly", priority: 0.4 },
  ];

  const annonces: MetadataRoute.Sitemap = ANNONCES.map((a) => ({
    url: `${base}/annonces/${a.slug}`,
    lastModified: a.date ? new Date(a.date) : now,
    changeFrequency: "yearly",
    priority: 0.5,
  }));

  const cas: MetadataRoute.Sitemap = CAS_LIST.map((c) => ({
    url: `${base}/cas-usage/${c.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.6,
  }));

  return [...staticRoutes, ...annonces, ...cas];
}
