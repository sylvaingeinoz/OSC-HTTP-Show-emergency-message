# Démarrage propre et lancement automatique

## Ce que configure la version 1.1

1. **Noyau et firmware** : désactivation du splash arc-en-ciel pris en charge par le firmware, suppression du splash système, des logos Linux et du curseur de console. Messages de démarrage réduits et console HDMI déplacée vers tty3 ; les paramètres de partition racine, stockage et console série sont préservés.
2. **Connexion automatique** : LightDM ouvre directement la session Wayland `stop-show`, avec le compte utilisé pour installer. Aucune saisie sur le Pi n’est nécessaire.
3. **Session dédiée** : labwc lit `/etc/stop-show/labwc`, sans autostart du bureau Raspberry Pi. Ni barre de tâches, ni gestionnaire de fichiers, ni serveur de notifications, ni économiseur d’écran n’est lancé. Un fond noir est créé par swaybg.
4. **Curseur** : thème Xcursor transparent chargé avant le lancement du compositeur, complété par `cursor: none` dans l’écran de scène.
5. **Navigateur** : Chromium en kiosque avec profil temporaire neuf à chaque lancement, sans première visite ni restauration d’une session interrompue. Le profil est nettoyé à sa fermeture et le répertoire runtime disparaît au redémarrage.
6. **Page locale noire** : le kiosque ouvre le fichier local d’affichage, qui interroge le service en boucle. Une panne ou lenteur HTTP ne conduit pas à une page d’erreur du navigateur : l’écran reste noir. Seule la lecture de l’état public possède un en-tête CORS autorisant cette page locale ; les commandes sont accessibles sans clé sur le réseau de régie.
7. **Relance** : systemd relance le serveur et Chromium après leur arrêt. Le lanceur de session relance labwc après sa sortie. À chaque démarrage complet, LightDM recrée la session puis démarre le service et le kiosque.

L’application reste au noir jusqu’à réception d’une consigne valide. Elle ne réaffiche pas une consigne ancienne après un redémarrage.

## Fichiers et supervision

- Application : `~/.local/share/stop-show/app`
- Réglages persistants : `~/.local/share/stop-show/data`
- Session système : `/usr/share/wayland-sessions/stop-show.desktop`
- Lanceur graphique : `/usr/local/bin/stop-show-desktop`
- Paramètres de session : `/etc/stop-show/labwc`
- Services utilisateur : `stop-show-session.target`, `stop-show.service`, `stop-show-kiosk.service`
- Sauvegardes avant modification : `/var/lib/stop-show-install`

Depuis SSH, connecté avec le compte de l’installation :

```sh
systemctl --user status stop-show.service stop-show-kiosk.service
journalctl --user -u stop-show.service -u stop-show-kiosk.service -b --no-pager
sudo journalctl -u lightdm -b --no-pager
```

Relancer l’afficheur et le serveur :

```sh
systemctl --user restart stop-show-session.target
```

La reconnexion SSH n’est pas nécessaire pour l’exploitation ; elle sert à l’installation et au dépannage. Le redémarrage automatique ne dépend pas d’une connexion SSH maintenue ouverte.

## Retour au bureau

Depuis SSH :

```sh
bash ~/.local/share/stop-show/app/pi/restore-desktop.sh
sudo reboot
```

Le script restaure les fichiers système sauvegardés lors de la première installation 1.1 et retire ceux ajoutés pour la session dédiée. Il conserve l’application, les réglages et les sauvegardes. Les modifications système faites manuellement sur ces mêmes fichiers après l’installation seront remplacées par la sauvegarde initiale : en garder une copie si nécessaire. LightDM reste activé et la cible de démarrage reste graphique.

Si SSH est indisponible, monter la carte sur un autre système Linux et restaurer les fichiers sauvegardés depuis `var/lib/stop-show-install/files` selon le manifeste `manifest.json`. Les fichiers dont la valeur du manifeste est `null` ont été créés par l’installateur et peuvent être retirés. Réparer d’abord le réseau ou la configuration du démarrage avant de reprendre l’exploitation.

## Ce qui doit être vérifié sur le Pi et la TV

Ce dispositif réduit les éléments visibles **à partir de la prise en charge par Raspberry Pi OS**. Il ne peut pas masquer :

- Le logo du fabricant de la TV, la détection d’entrée, « Aucun signal » ou le changement de résolution.
- Des diagnostics du bootloader, une erreur de carte, de système, de connexion automatique ou de pilote graphique.
- Une brève transition pendant la prise de contrôle de la sortie par le firmware, le noyau, Wayland ou Chromium selon leurs versions.
- Un écran de connexion d’urgence si LightDM lui-même ne parvient pas à démarrer la session.

L’installateur ne modifie pas l’EEPROM du Pi ni les réglages propres à la TV. Sur la TV, sélectionner la bonne entrée, désactiver les messages d’entrée si possible, l’écran de veille, la veille automatique et le zoom/overscan. Pour garantir un noir absolu dès l’arrivée du public, allumer et vérifier le système avant son entrée, ou utiliser une fonction de masquage matérielle de la chaîne vidéo.

La configuration et les fonctions de restauration sont testées sur des fichiers factices ; **aucun Pi n’était disponible pour tester un démarrage à froid**. La recette doit vérifier plusieurs démarrages et coupures, la relance de Chromium, le retour après panne du service et le fonctionnement prolongé. Le comportement de chaque version de Chromium/LightDM et du téléviseur reste à confirmer sur place.

## Sources techniques

- [Raspberry Pi : options du firmware](https://www.raspberrypi.com/documentation/computers/config_txt.html)
- [Raspberry Pi : configuration du système](https://www.raspberrypi.com/documentation/computers/configuration.html)
- [LightDM : options de session automatique](https://github.com/ubuntu/lightdm/blob/main/data/lightdm.conf)
- [labwc : sélection du dossier de configuration et gestion de session](https://labwc.github.io/labwc.1.html)
- [Format Xcursor](https://manpages.debian.org/trixie/libxcursor-dev/XcursorFilenameSaveImages.3.en.html)
