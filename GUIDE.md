# Guide complet — STOP SHOW

Version 1.2 · interface et documentation en français · 29 septembre 2026.

Une télévision HDMI affiche les consignes envoyées depuis la régie web ou Bitfocus Companion. Le Pi ouvre automatiquement une session graphique dédiée, sur fond noir, avec Chromium plein écran. Aucun bureau ni panneau n’est lancé dans cette session. Aucun clavier n’est nécessaire après la préparation de la carte et l’installation par SSH.

## Contenu et démarrage rapide sur ordinateur

- `server.py` : service Python, commandes HTTP/OSC, réglages persistants, pilotage HDMI.
- `static/` : régie web et écran de scène ; aucun service externe, police distante ou dépendance JavaScript.
- `install.sh` : point d’entrée d’installation depuis le dépôt ou après téléchargement.
- `pi/` : installation, session dédiée, démarrage, sauvegarde et restauration de la configuration système.
- `COMPANION.md` : actions HTTP/OSC prêtes à recopier.
- `VALIDATION.md` : vérifications réalisées et recette matérielle restante.

Pour essayer avec Python 3.9 ou ultérieur, depuis ce dossier :

```sh
python3 server.py --data .data
```

Ouvrir [la régie locale](http://127.0.0.1:8080) ; aucun identifiant ni clé n’est nécessaire. [L’écran de scène](http://127.0.0.1:8080/display) fonctionne dans un second onglet. L’ordinateur n’a pas besoin de Wayland pour essayer les consignes ; le panneau HDMI indiquera honnêtement son indisponibilité. Arrêt : Ctrl+C.

## Comportement de l’afficheur

| Fonction | Comportement |
| --- | --- |
| Message / prompteur fixe | Texte multiligne centré, retours à la ligne conservés ; jusqu’à 8 000 caractères. Aucun défilement. |
| STOP SHOW | Message blanc sur fond rouge alternant avec un rouge sombre ; période réglable de 500 à 3 000 ms. |
| REPRISE | Raccourci envoyant le texte « REPRISE ». |
| Heure | Horloge 24 h du Pi dans le fuseau choisi ; secondes visibles. |
| Minuterie | Durée en secondes, affichage HH:MM:SS, arrêt à zéro. Horloge monotone pour résister aux corrections de l’heure système. |
| Compte à rebours | Date et heure cible explicites avec décalage UTC, affichage HH:MM:SS, arrêt à zéro. |
| Noir | Noir immédiat ; signal HDMI conservé, téléviseur toujours allumé. |
| Mire | Cadre, croix centrale, trois plages de gris et repères discrets pour préparer l’écran. |
| Témoin | Optionnel, désactivé par défaut. Petit point vert même au noir ; ambre en cas de perte de liaison au service. |

**Retour au noir : 15 secondes par défaut.** Chaque consigne valide reçue remplace la précédente et repart pour le délai complet. STOP SHOW respecte exactement cette règle et ne possède aucun verrouillage. La mire, l’horloge et les compteurs suivent aussi le délai. Les lectures d’état ne réarment rien. **0 désactive le retour automatique au noir, même pour STOP SHOW et une consigne déjà visible.** Repasser de 0 à un délai positif démarre ce délai pour la consigne visible. Changer entre deux délais positifs ne réarme pas la consigne en cours. Une consigne déjà éteinte ne réapparaît pas. Une commande invalide ne change pas l’affichage.

« Prolonger la consigne actuelle » / `keepalive` repart pour un délai complet sans remettre à zéro la minuterie ou la cible. Il ne ressuscite pas une consigne déjà éteinte. Pour garder une horloge, une mire ou un compteur pendant longtemps, mettre le délai à 0, augmenter le délai avant de l’envoyer, ou envoyer `keepalive` périodiquement, par exemple toutes les 5 secondes pour un délai de 15 secondes. Ne pas répéter `timer` : cela redémarrerait la durée.

La police se choisit entre sans empattement, serif et monospace. La taille est un maximum exprimé en pixels pour une hauteur d’écran de 1 080 pixels, proportionnel aux autres résolutions. Le texte se réduit automatiquement pour tenir entièrement dans les marges : un texte très long devient petit. Privilégier des consignes courtes et vérifier la lisibilité à la distance réelle.

L’écran interroge le service toutes les 200 ms environ. En cas de perte de liaison au service, il passe au noir au plus tard après deux secondes sans réponse ou à l’échéance de la consigne si elle arrive avant. Un redémarrage du service repart toujours au noir ; les consignes ne sont pas sauvegardées. Le témoin indique la liaison navigateur–service, pas la présence du signal HDMI, la réception effective sur le téléviseur ou l’état de Companion.

## Installation sans clavier sur le Pi

### 1. Préparer la carte avec Raspberry Pi Imager

**Ne pas utiliser NOOBS pour ce projet.** Le dépôt officiel précise que NOOBS n’est plus pris en charge ni recommandé et renvoie vers Imager. Il a été archivé en février 2023. Il ne fournit pas une base prise en charge pour cette installation Pi 5. [Source officielle NOOBS](https://github.com/raspberrypi/noobs).

Sur l’ordinateur de préparation, installer [Raspberry Pi Imager](https://www.raspberrypi.com/software/), sélectionner **Raspberry Pi 5**, puis **Raspberry Pi OS 64 bits avec bureau** proposé pour ce modèle. L’installateur réutilise le gestionnaire de connexion LightDM de cette édition : ne pas sélectionner Lite. Le bureau fourni ne sera pas lancé dans la session de spectacle. Personnaliser le nom d’hôte `stopshow`, le compte utilisateur (exemple `regie`), le mot de passe, le pays Wi-Fi et les identifiants réseau si besoin, ainsi que SSH, de préférence avec une clé. Écrire la carte puis démarrer le Pi. Le guide officiel décrit la préparation des accès à distance dans Imager. [Installation officielle](https://www.raspberrypi.com/documentation/computers/getting-started.html).

Brancher la TV en HDMI avant le démarrage, utiliser une alimentation adaptée au Pi 5, et privilégier Ethernet sur le réseau de régie. Cette version cible **un seul téléviseur connecté**, pour que Chromium apparaisse sur la bonne sortie. Le second HDMI n’est pas utilisé pour un affichage indépendant.

### 2. Installer depuis GitHub

Se connecter par SSH avec le compte créé dans Imager, puis suivre [les deux commandes du README](README.md#installation-sur-le-pi).

Le script télécharge le dépôt public indiqué, installe les paquets nécessaires via les dépôts Raspberry Pi OS, copie l’application dans `~/.local/share/stop-show/app` et configure LightDM pour ouvrir automatiquement la session **Stop Show**. Cette session utilise son propre labwc, sans bureau, panneau, économiseur d’écran ni démon de notifications. Deux services utilisateur supervisent le service HTTP/OSC et Chromium. Le lanceur de session relance labwc s’il se termine.

Les fichiers système modifiés sont sauvegardés une seule fois sous `/var/lib/stop-show-install`. Relancer l’installateur met à jour le logiciel en conservant les réglages dans `~/.local/share/stop-show/data`. Le nouvel installateur retire uniquement son ancien ajout d’autostart v1.0, en conservant une sauvegarde. Un redémarrage est nécessaire pour activer ou mettre à jour la session dédiée. L’installation ne redémarre pas le Pi automatiquement.

Le script demande `sudo` pour installer les paquets et configurer le système. Il ne modifie ni les accès SSH, ni le Wi-Fi, ni le nom d’hôte. L’accès SSH doit déjà fonctionner, car le Pi devient un afficheur dédié. La session choisit directement labwc ; aucune sélection manuelle Wayland/X11 n’est nécessaire sur l’image prise en charge.

### 3. Connecter la régie

Ouvrir `http://stopshow.local:8080` depuis l’ordinateur, tablette ou téléphone du même réseau. La régie est immédiatement utilisable, sans connexion ni clé. La TV doit être noire après le chargement ; envoyer une mire pour confirmer son fonctionnement.

Ports par défaut : TCP 8080 (web et HTTP), UDP 9000 (OSC). Le script Pi écoute toutes les interfaces IPv4. Le démarrage manuel écoute seulement `127.0.0.1`, sauf si `--host 0.0.0.0` est ajouté. Les changements de ports s’effectuent dans le service et le lanceur Chromium, pas dans la régie web.

## Résolution, fréquence, rotation et inversion

Le panneau HDMI utilise **`wlr-randr` dans la session Wayland réelle**. Le démarrage importe le nom du socket Wayland fourni par labwc ; aucun `wayland-0` n’est supposé. La résolution et la fréquence sont liées dans une liste de modes annoncés par la TV : 59,94 Hz et 60 Hz sont distincts. Aucun mode arbitraire ni modification de `config.txt` n’est inventé.

Choisir la sortie active et un mode, puis une transformation : normal, 90°, 180°, 270°, miroir horizontal ou miroir combiné à une rotation. « Miroir + 180° » correspond à une inversion verticale. Le sens exact combiné doit être vérifié avec la mire. Ce réglage transforme la sortie vidéo entière, pas seulement le texte de l’application.

Cliquer **Essayer pendant 20 secondes**, regarder la TV, puis **Confirmer l’image sur la TV**. Sans confirmation, le service tente de restaurer le mode précédent. Seuls les réglages confirmés sont enregistrés et réappliqués au démarrage. Si la TV a changé ou n’annonce plus le mode, le service conserve le mode courant et signale l’échec dans les diagnostics. Le délai de retour arrière dépend du service en fonctionnement ; une coupure de courant ou une panne du compositeur ne peut pas être corrigée par ce mécanisme.

Le Pi 5 peut prendre en charge des sorties allant jusqu’à 4K à 60 Hz, mais les modes utilisables dépendent de la TV, du câble, de l’adaptateur et du système. La présence d’un mode dans la liste ne garantit pas sa qualité visuelle. Vérifier le signal après chaque changement. [Capacités et réglages officiels](https://www.raspberrypi.com/documentation/computers/configuration.html#set-resolution-and-rotation).

La mire indique les dimensions de la zone du navigateur, pas une mesure de la fréquence physique. L’aperçu de la régie n’est pas une capture HDMI ; il ne montre pas la transformation de sortie. Les rotations du bureau avant lancement, l’overscan de la TV, HDR, CEC et la gestion de plusieurs écrans ne sont pas administrés par cette version. Régler la TV en affichage intégral / sans zoom et désactiver sa propre veille automatique avant la représentation.

## Heure cible, notamment minuit au Nouvel An

Pour minuit en Suisse entre le 31 décembre 2026 et le 1er janvier 2027 :

```json
{"mode":"countdown","target":"2027-01-01T00:00:00+01:00"}
```

La date complète évite l’ambiguïté « ce soir ou demain ». Le décalage est obligatoire. Pour une date d’été en Suisse, le décalage usuel est `+02:00` ; choisir celui correspondant à la cible. La zone des réglages contrôle l’horloge affichée, tandis que la cible contient son propre décalage.

Le compte à rebours utilise l’heure du Pi, et non celle du téléphone. Contrôler sa synchronisation par SSH :

```sh
timedatectl status
sudo timedatectl set-ntp true
```

En réseau fermé, prévoir une source de temps NTP accessible ou régler et vérifier l’heure avant l’événement. La synchronisation NTP et l’autonomie de l’horloge matérielle ne sont pas assurées par l’application. Pour une cible longue, penser à prolonger l’affichage ou augmenter le délai au noir.

## Exploitation et dépannage

Depuis SSH, dans le même compte utilisateur que la session Stop Show :

```sh
systemctl --user status stop-show.service stop-show-kiosk.service
journalctl --user -u stop-show.service -u stop-show-kiosk.service -n 80 --no-pager
systemctl --user restart stop-show.service stop-show-kiosk.service
```

- Régie inaccessible : vérifier l’IP, le port, le réseau et le démarrage de la session Stop Show. Les services sont démarrés par la session graphique.
- HDMI indisponible : vérifier labwc, la TV allumée au démarrage, `wlr-randr` installé et le compte de session. Ne pas lancer le service avec `sudo`.
- Essai non confirmé : recharger la liste HDMI pour consulter le résultat du retour arrière.
- Mauvais mode enregistré : arrêter le service, sauvegarder `~/.local/share/stop-show/data/settings.json`, mettre son champ `hdmi` à `null`, puis redémarrer le Pi pour reprendre le mode du compositeur.
- Minuterie disparue : vérifier le délai au noir. Les compteurs n’en sont pas exemptés.
- OSC sans effet : vérifier l’adresse `/show/...`, l’UDP 9000, les arguments et leurs types. `/api/diagnostics` expose les compteurs reçus/rejetés sans authentification.
- Témoin absent : il est désactivé par défaut. Un point ambre signifie que l’écran a perdu le service.
- Bureau visible : la session dédiée Stop Show n’a pas été sélectionnée ; consulter `sudo journalctl -u lightdm -b` et `/etc/lightdm/lightdm.conf`. Voir aussi [les limites du démarrage propre](DEMARRAGE.md).

Pour mettre à jour un Pi déjà installé en 1.1, suivre [les commandes de mise à jour du README](README.md#mise-à-jour-dun-pi-déjà-installé-en-version-11). Les réglages restent dans `data/` et sont préservés. Sauvegarder ce dossier pour conserver la configuration ; les consignes en cours ne sont jamais enregistrées.

Pour revenir à la configuration système sauvegardée, depuis SSH :

```sh
bash ~/.local/share/stop-show/app/pi/restore-desktop.sh
sudo reboot
```

Les fichiers système créés sont retirés et ceux qui existaient sont restaurés depuis la sauvegarde initiale. L’application et les réglages restent présents. La cible de démarrage demeure graphique et LightDM reste activé ; choisir le mode console dans `raspi-config` si souhaité. Après migration depuis v1.0, l’ancien lancement automatique v1.0 reste désactivé afin de retrouver le bureau normal.

## Réseau et limites de cette première version

La régie, les commandes HTTP/OSC et les réglages sont accessibles sans clé ni compte sur le réseau de régie. La sécurité SSH reste inchangée. HTTP et OSC ne sont pas chiffrés : utiliser un réseau local de confiance, ne pas exposer ces ports sur Internet. Il n’y a ni compte par opérateur, ni TLS intégré, ni journal des consignes. Les datagrammes OSC n’offrent pas de garantie de livraison ; HTTP fournit un accusé de réception logiciel, sans confirmer ce que montre physiquement la TV.

STOP SHOW est une consigne visuelle de régie. Il ne déclenche aucune coupure électrique ou arrêt machine. L’application n’a actuellement été essayée sur aucun Pi réel ; voir la recette de validation matérielle avant une représentation.
