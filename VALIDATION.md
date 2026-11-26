# Validation — versions 1.0 à 1.3

Les sections 1.0 et 1.1 ci-dessous décrivent les essais historiques, avant suppression de la clé en 1.2.

## Réalisé localement le 15 septembre 2026

Environnement : macOS, Python 3.9.6, navigateur Chromium intégré à Codex. Aucun Raspberry Pi ni téléviseur connecté à cette tâche.

### Tests automatisés : 20 réussis

Commande reproductible, depuis le dossier du projet :

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Les tests couvrent :

- Démarrage noir, clé privée conservée entre redémarrages et absente de l’état public.
- Extinction de tous les modes au délai exact, STOP SHOW inclus.
- Réarmement par une consigne identique ; absence de réarmement par lecture d’état ou réglage.
- Prolongation sans redémarrage du compteur ; absence de résurrection d’une consigne expirée.
- Remplacement de STOP SHOW par une consigne normale et noir immédiat.
- Minuterie indépendante des sauts de l’horloge système.
- Cible datée avec décalage obligatoire, rejet d’une cible passée et arrêt à zéro.
- Validation des entrées, conservation de l’état après rejet, persistance des réglages et échec d’écriture sans modification en mémoire.
- HDMI simulé : détection des modes, rejet d’un mode non annoncé, confirmation, sauvegarde, retour arrière et refus d’une confirmation trop tardive.
- Commandes système transmises sans interpréteur de commandes.
- Décodage OSC et authentification ; rejet des paquets malformés.
- **Vrais échanges locaux HTTP et UDP** : livraison des consignes, refus sans clé, types de contenu, pages statiques et refus de chemins hors de l’application.

La syntaxe Python avait aussi été vérifiée. Le contrôle individuel de tous les scripts de lancement est réalisé dans la validation 1.1 ci-dessous. Les scripts Pi n’ont pas été exécutés sur macOS.

### Contrôle dans un navigateur

- Connexion par clé, chargement et enregistrement des réglages.
- Envoi d’un message multiligne depuis la régie, aperçu conforme.
- STOP SHOW rouge clignotant ; retour au noir avec délai réglé à trois secondes ; témoin restant visible.
- Mire avec dimensions et repères ; horloge dans le fuseau choisi.
- Minuterie de trois secondes observée à `00:00:03`, puis `00:00:00`.
- Cible du 1er janvier 2027 affichée sous forme de compte à rebours.
- Affichage à 1 280 × 720 et 1 920 × 1 080. Un défaut d’arrondi réduisant le texte à certaines largeurs a été trouvé puis corrigé et revérifié visuellement.
- Message de 50 lignes ajusté sans dépassement : hauteur mesurée 633 px pour une zone de 633,6 px disponible à 720p.
- Régie en largeur mobile 390 px : aucun débordement horizontal observé.
- HDMI indisponible signalé explicitement sur macOS.
- Arrêt du service pendant une consigne : écran redevenu noir et témoin ambre.

L’instrumentation du navigateur a signalé une erreur `MutationObserver` sans URL source pendant les essais. Le code de l’application n’utilise pas `MutationObserver` ; les interactions décrites ci-dessus ont abouti. Cela n’a pas servi à conclure à l’absence globale d’erreurs de console.


## Ajouts de la version 1.1 — 16 septembre 2026

**29 tests réussis localement** : les 20 tests initiaux, 8 tests d’installation et 1 test d’accès de la page locale à l’état public.

Vérifications supplémentaires :

- Installation répétée donnant les mêmes fichiers sans écraser les sauvegardes initiales.
- Restauration exacte des fichiers antérieurs et retrait des fichiers de session ajoutés ; restauration répétable.
- Conservation des paramètres de partition racine et de console série, ligne de démarrage unique.
- Rejet d’une ligne de démarrage invalide avant toute modification.
- Sélection de la session dédiée même si LightDM possède une section spécifique de siège.
- Fichier de curseur transparent conforme à la structure Xcursor ; XML de session valide.
- Absence de programmes de bureau et de veille dans l’autostart dédié ; rejet d’un nom d’utilisateur invalide.
- Lecture HTTP de l’état public avec origine locale `null`, commandes toujours interdites sans clé et sans ouverture CORS des commandes.
- Syntaxe de chaque lanceur Bash et des scripts d’autostart/arrêt vérifiée individuellement.

Le contrôle intégré du navigateur interdit les URL `file://` : le chargement du nouvel écran local de kiosque n’a donc pas été testé dans ce navigateur. Il reste à vérifier sur le Pi avec sa version de Chromium, notamment l’accès au service loopback, le fond noir avant connexion et la reprise du service. L’écran HTTP et le fonctionnement de l’application avaient été vérifiés dans la version 1.0 ; la page partage les mêmes composants.

Une configuration GitHub Actions exécute la suite Python et le contrôle de syntaxe à chaque publication. Son résultat distant est à consulter dans l’onglet Actions du dépôt.

## Version 1.2 — 29 septembre 2026

**35 tests automatisés réussis**, avec échanges HTTP/UDP réels locaux. Syntaxe de chaque script Bash vérifiée.

- Accès direct à la régie, aux commandes et aux réglages sans clé ; ancien fichier de clé ignoré, réglages conservés.
- OSC sans premier argument de clé ; contrôle des arguments invalides.
- `off_time=0` : tous les modes restent actifs, STOP SHOW compris ; bascule pendant une consigne, réactivation d’un délai positif, noir immédiat et aucune résurrection d’une consigne expirée.
- Mise à jour simulée d’une installation : réglages et services inchangés, sauvegarde du code antérieur, restauration en cas d’échec du remplacement.
- Navigateur : régie directement accessible, enregistrement de 0, STOP SHOW toujours visible au-delà de 15 secondes et état « Retour au noir désactivé ». Noir manuel vérifié, puis extinction après réactivation d’un délai positif.
- Mire contrôlée visuellement à 1280 × 720 : cadre, croix centrale, trois plages de gris et repères discrets.

La mise à jour sur un vrai Pi, la page locale du kiosque et le signal HDMI restent à vérifier sur place. Le délai 0 ne désactive pas le noir en cas de perte du service.

## Non validé faute de matériel

- Installation des paquets sur l’image Raspberry Pi OS réellement choisie.
- Démarrage à froid avec la session dédiée LightDM/labwc, page locale Chromium en kiosque et relance par systemd.
- Disponibilité effective de `wlr-randr` et de son protocole dans la session du Pi.
- Lecture EDID de la TV, changement réel de résolution/fréquence, rotation et miroirs ; restauration HDMI réelle.
- Lisibilité à la distance des comédiens, latence réelle et clignotement sur le téléviseur.
- Configuration dans une instance Bitfocus Companion réelle : exemples documentés, protocole testé localement, module non piloté pendant ces essais.
- Fonctionnement continu, stabilité thermique, coupures d’alimentation, déconnexion/reconnexion HDMI et précision temporelle sur le réseau de spectacle.

## Recette à réaliser avant une représentation

1. Installer depuis Imager et démarrer avec TV branchée, sans clavier. Vérifier accès SSH et régie web après redémarrage.
2. Envoyer la mire, vérifier bords, sens, croix centrale et plages de gris, absence de zoom et de veille TV. Confirmer une résolution/fréquence supportée.
3. Essayer 90°, 180°, 270° et les miroirs utiles. Tester le retour arrière sans confirmer, puis confirmer un réglage et redémarrer pour vérifier sa persistance.
4. Laisser le délai à 15 secondes. Envoyer message puis STOP SHOW ; vérifier que chacun s’éteint au même délai. Renvoyer à 10 secondes et vérifier le nouveau délai complet.
5. Mettre le délai à 0, vérifier que STOP SHOW reste affiché au-delà de 15 secondes, puis réactiver un délai positif. Vérifier REPRISE après STOP SHOW, noir immédiat, témoin activé/désactivé et longs textes depuis la distance de scène.
6. Tester chaque bouton HTTP et OSC dans Companion, sans clé. Vérifier l’adresse réseau stable.
7. Tester une minuterie, une cible dans quelques minutes, puis la cible finale de minuit avec l’heure du Pi synchronisée. Vérifier la prolongation sans redémarrer les compteurs.
8. Couper la liaison au service pour confirmer noir et témoin ambre ; redémarrer le service pour confirmer retour au noir et reprise des nouvelles commandes.
9. Laisser le système fonctionner pendant une durée au moins égale au spectacle, avec répétition des consignes et contrôle de la veille, du réseau et de la température.

La validation matérielle reste à effectuer ; les tests locaux ne la remplacent pas.

## Version 1.3 — 26 novembre 2026

**47 tests réussis localement**, dont les fonctions antérieures (HTTP/OSC sans clé, délai 0, HDMI simulé, installation et restauration), plus :

- Recherche sans installation implicite, version et commit épinglés, erreur réseau supprimant la proposition périmée.
- Refus d’URLs, de commandes et de révisions fournies par le client HTTP.
- Exclusion mutuelle par verrou, échec de lancement et statut exploitable.
- Archive valide téléchargée simulée, rejet des chemins sortants et révisions arbitraires ; contrôle d’importation du serveur.
- Remplacement, sauvegarde, préservation exacte des réglages, restauration de l’ancien code après échec du contrôle de santé.
- Vrai processus du nouveau serveur démarré depuis le dossier remplacé, réponse HTTP portant la révision attendue, réglage 0 relu et fichier conservé à l’identique. Les commandes systemd sont simulées dans ces tests macOS.
- Syntaxe Bash et JavaScript vérifiée.
- Navigateur à 1280 × 720 : texte « TV INFO CAST » grand et centré, cadre/croix/gris préservés, réglage 0 et mire active ; panneau OTA affichant version et boutons, recherche et affichage d’erreur vérifiés.

À vérifier sur le Pi : lancement de l’unité systemd indépendante, arrêt/reprise du kiosque, chargement de sa page locale, signal HDMI, reprise après coupure électrique et cycle OTA entre deux commits publiés. Le contrôle HTTP ne garantit pas l’image sur le téléviseur.

## Correctif 1.3.1 — proposition Google Translate

Les deux pages déclarent `translate="no"` et `<meta name="google" content="notranslate">`. Ce dernier mécanisme empêche Chromium de proposer la traduction de la page ([documentation Chromium](https://chromium.googlesource.com/website/+/HEAD/site/developers/design-documents/translate/index.md)). La correction est dans les fichiers HTML, donc livrée par OTA même aux Pi dont le lanceur Chromium est une copie antérieure. Aucun changement des réglages ou du système.

Structure HTML et numéro de version vérifiés localement. La disparition de la bulle dans la version Chromium du Pi reste à confirmer après installation et relance automatique du kiosque.
