# July 2021 Gaspar vs JRC Mismatch Evidence Report

## Purpose

This note documents a targeted external-source audit of the largest `Gaspar-only`
and `JRC-only` commune clusters visible in the France comparison app for
**July 2021**.

The goal is not to prove every individual mismatch row one by one. The goal is
to test whether the largest disagreement areas correspond to real flood
evidence visible in public sources such as:

- local and regional news
- prefecture or ministry pages
- `Legifrance` catastrophe-naturelle decrees
- hydrologic evidence such as `Reperes de crues`

This audit was carried out on **June 4, 2026**.

## Local Comparison Snapshot

For the app filter `Comparison -> Year 2021 -> Month 07`, the local comparison
snapshot used for this note was:

- `Both active`: `133`
- `Gaspar only`: `363`
- `JRC only`: `1,175`

These values come from the local app outputs, not from the external web sources.

## Method

The search strategy was intentionally targeted rather than exhaustive:

- identify the biggest mismatch clusters from the local comparison outputs
- search by `commune`, nearby `town/city`, and `department`
- prefer official or primary sources when available
- use local news as supporting evidence where official commune-level detail is
  not published

Important limitation:

- media coverage is often cluster-level, not commune-by-commune
- official decrees can be commune-level, but not every flooded area appears in
  a decree at the same time or under the same administrative logic
- some JRC detections may reflect broader floodplain or agricultural inundation
  that does not surface in Gaspar

## Findings

### 1. Gaspar-only cluster: Jura `(39)` around Arbois, Lons-le-Saunier, Bletterans

Evidence strength: `strong`

What was found:

- `Le Progres` reported repeated flooding in the Jura on **July 16-17, 2021**,
  including the `Arbois` sector and interventions in `Lons-le-Saunier`.
- A later official basin report also mentions flood impacts in
  `Lons-le-Saunier` and `Bletterans`.
- The official CatNat decree of **July 23, 2021** explicitly includes
  `Arbois` and `Lons-le-Saunier` for `inondations et coulees de boue`.

Interpretation:

- This is strong evidence that at least part of the `Gaspar-only` Jura cluster
  corresponds to real July 2021 flood impacts.
- If JRC misses some of these communes, the difference is more likely linked to
  flood footprint detection limits, urban runoff behavior, or event geometry
  than to a false Gaspar signal.

Sources:

- [Le Progres, 16 July 2021](https://www.leprogres.fr/environnement/2021/07/16/inondations-glissement-de-terrain-le-departement-prend-l-eau)
- [Le Progres, 17 July 2021](https://www.leprogres.fr/environnement/2021/07/17/inondations-trois-cents-appels-en-une-heure-trente)
- [Official Rhone-Mediterranee basin event report](https://www.auvergne-rhone-alpes.developpement-durable.gouv.fr/IMG/pdf/20240606-epri-bassinrm-receuil_evts.pdf)
- [Legifrance, Arrete du 23 juillet 2021](https://www.legifrance.gouv.fr/jorf/id/JORFSCTA000043879099)

### 2. Gaspar-only cluster: Meuse `(55)` around Bar-le-Duc and Behonne

Evidence strength: `strong`

What was found:

- Local reporting on **July 15, 2021** clearly shows `Bar-le-Duc` under water.
- The official CatNat decree includes both `Bar-le-Duc` and `Behonne` for
  floods dated **July 13-15, 2021**.
- The Meuse prefecture published the catastrophe-naturelle request procedure
  specifically for the **July 13-15, 2021** floods.

Interpretation:

- This is strong evidence for a real flood event affecting the Meuse cluster.
- If some communes in this cluster are absent from JRC, the mismatch is not
  sufficient on its own to dismiss the Gaspar signal.

Sources:

- [L'Est Republicain, 15 July 2021](https://www.estrepublicain.fr/faits-divers-justice/2021/07/15/inondations-spectaculaires-a-bar-le-duc-la-ville-toute-une-journee-les-pieds-dans-l-eau)
- [Radio Latitude, 15 July 2021](https://www.latitude.fm/2021/07/15/meuse-bar-le-duc-sous-les-eaux-apres-de-fortes-pluies/)
- [Legifrance, Arrete du 23 juillet 2021](https://www.legifrance.gouv.fr/jorf/id/JORFSCTA000043879099)
- [Meuse prefecture, July 13-15, 2021 flood procedure](https://www.meuse.gouv.fr/Politiques-publiques/Securite/Demande-de-catastrophes-naturelles-Inondations-du-13-au-15-juillet-2021)

### 3. Gaspar-only cluster: Seine-et-Marne `(77)` around Claye-Souilly

Evidence strength: `moderate to strong`

What was found:

- Local reporting on **July 14, 2021** names `Claye-Souilly` and several other
  flooded communes in the north of Seine-et-Marne.
- The reporting describes road closures, flooded basements, and multiple fire
  service interventions.

Interpretation:

- This supports a real flood impact in the `Claye-Souilly` area.
- The available evidence found here is more media-based than decree-based for
  this exact July cluster, so the evidence is slightly less direct than in the
  Jura or Meuse examples.

Sources:

- [Magjournal77, 14 July 2021](https://magjournal77.fr/vie-locale/item/55210-seine-et-marne-inondations-au-nord-le-departement-a-mobilise-ses-equipes-d-intervention/)
- [Le Parisien, 14 July 2021](https://www.leparisien.fr/seine-et-marne-77/le-nord-de-la-seine-et-marne-a-nouveau-frappe-par-les-inondations-on-nettoie-on-fait-ce-quon-peut-14-07-2021-EHY6AXVSHBEJDPHUDNOCFF7M5I.php)

### 4. JRC-only cluster: Haute-Saone `(70)` with Autet and nearby communes

Evidence strength: `moderate`

What was found:

- A local article on **July 25, 2021** reports cleanup in `Autet` after water
  invasion.
- The department was under active flood vigilance on **July 14-16, 2021** on
  the `Ognon` sector, which is consistent with broader hydrologic disturbance.

Interpretation:

- This supports the idea that at least part of the `JRC-only` Haute-Saone
  cluster corresponds to genuine flood activity.
- The evidence found is strongest for `Autet` and for department-level
  conditions, not for every single JRC-only commune in the cluster.

Sources:

- [L'Est Republicain, Autet, 25 July 2021](https://www.estrepublicain.fr/environnement/2021/07/25/nettoyage-apres-l-invasion-d-eau)
- [L'Est Republicain, Ognon vigilance, 14 July 2021](https://www.estrepublicain.fr/faits-divers-justice/2021/07/14/risque-de-crues-vigilance-sur-l-ognon-en-amont-de-la-linotte)
- [macommune.info, prefecture advice summary, 16 July 2021](https://www.macommune.info/vigilance-orange-aux-crues-sur-lognon-et-orages-en-haute-saone-les-conseils-de-la-prefecture/)

### 5. JRC-only cluster: Ardennes `(08)` around Asfeld and Sedan

Evidence strength: `moderate to strong`

What was found:

- `Champagne FM` reported pumping operations in `Asfeld` on **July 14, 2021**.
- `Radio 8 Ardennes` reported a continuing flood situation on **July 16, 2021**,
  including mention of `Sedan` and orange vigilance in affected basins.

Interpretation:

- This provides good evidence that the JRC-only Ardennes cluster is not just a
  spurious remote-sensing artifact.
- The strongest confirmation is cluster-level rather than a complete
  commune-by-commune validation.

Sources:

- [Champagne FM, 14 July 2021](https://www.champagnefm.com/news/a-deborde-56670)
- [Radio 8 Ardennes, 16 July 2021](https://radio8fm.com/infos/article/16614-Pluie_inondations_Point_de_situation_dans_les_Ardennes_ce_16_juillet_2021_a_19h00)

### 6. JRC-only floodplain sector: Aisne / Ardennes around Savigny-sur-Aisne and Vieux-les-Asfeld

Evidence strength: `strong`

What was found:

- The official `Reperes de crues` platform records a July 2021 flood mark at
  `Savigny-sur-Aisne`.
- The same platform records July 2021 flood evidence at `Vieux-les-Asfeld`,
  including floodwater reaching circulation areas.

Interpretation:

- This is strong site-level hydrologic evidence that the JRC flood footprint in
  this sector corresponds to a real event on the ground.
- This kind of evidence is especially useful because it is not just generic
  news coverage; it is flood-mark documentation.

Sources:

- [Reperes de crues, Savigny-sur-Aisne](https://www.reperesdecrues.developpement-durable.gouv.fr/site/lit-majeur-savigny-sur-aisne)
- [Reperes de crues, Vieux-les-Asfeld](https://www.reperesdecrues.developpement-durable.gouv.fr/site/sortie-du-village-en-direction-de-avaux)

### 7. JRC-only cluster: Saone-et-Loire `(71)` and the Seille / Louhans sector

Evidence strength: `moderate to strong`

What was found:

- The official government return-experience report states that, in
  `Saone-et-Loire`, a removable dike failed and flooded a town center during the
  July 2021 event.
- Local coverage on **July 17, 2021** documents the `Seille` flood in
  `Louhans-Chateaurenaud`.

Interpretation:

- This supports the JRC-only Saone-et-Loire cluster as a real flood signal.
- The evidence here is strongest at sector and department level; it does not by
  itself validate each commune individually.

Sources:

- [Official return-experience report page](https://www.economie.gouv.fr/cge/retour-inondations2021)
- [Full report PDF](https://www.economie.gouv.fr/files/files/directions_services/cge/media-document/retour-inondations2021.pdf)
- [L'Express / Louhans, 17 July 2021](https://www.lexpress.fr/societe/saone-et-loire-une-riviere-sort-de-son-lit-louhans-coupe-en-deux_2155128.html)

## Main Conclusion

The July 2021 mismatch between `Gaspar` and `JRC` is not just noise.

This targeted audit found external support for both:

- `Gaspar-only` clusters
- `JRC-only` clusters

That means the disagreement should be interpreted cautiously:

- `Gaspar` reflects an administrative recognition logic at commune level
- `JRC` reflects a flood footprint or hydrologic signal logic

As a result:

- Gaspar can contain real runoff, mudflow, or urban-flood impacts that a
  satellite-based product misses
- JRC can capture broader inundation, floodplain spread, or agricultural impact
  that does not appear in Gaspar at commune level

## Practical Reading of the Mismatch

A useful way to read the July 2021 differences is:

- `Gaspar-only` does not automatically mean false positive
- `JRC-only` does not automatically mean false positive
- cluster-level agreement with external evidence matters more than expecting a
  perfect commune-by-commune match
- administrative recognition and physical inundation are related, but they are
  not the same phenomenon

## Suggested Next Step

If deeper validation is needed, the next useful artifact would be a structured
evidence table with columns such as:

- `commune`
- `comparison_class`
- `department`
- `evidence_type`
- `evidence_scope`
- `source_title`
- `source_date`
- `url`
- `confidence`

That would make it easier to compare mismatch communes systematically rather
than only through narrative cluster notes.
