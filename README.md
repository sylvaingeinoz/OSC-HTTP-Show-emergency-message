# STOP SHOW · afficheur de scène

Un Raspberry Pi 5 derrière une télévision HDMI, piloté depuis une régie web ou **Bitfocus Companion en HTTP/OSC**. Interface en français, fonctionnement local, sans abonnement.

**Version 1.1 — installation et démarrage dédiés.** Le Pi ouvre automatiquement l’afficheur à chaque démarrage. La session ne lance aucun bureau, panneau ou notification ; elle utilise un fond noir et un curseur transparent. Le navigateur repart avec un profil temporaire neuf, et son écran local reste noir si le service met du temps à démarrer. [Détails et limites du démarrage](DEMARRAGE.md).

## Installation sur le Pi

**Une fois :** avec [Raspberry Pi Imager](https://www.raspberrypi.com/software/), écrire **Raspberry Pi OS 64 bits avec bureau**, adapté au Pi 5. Choisir un nom d’hôte (par exemple `stopshow`), créer un compte et activer SSH. Brancher la TV et le réseau, puis se connecter par SSH avec ce compte. NOOBS est abandonné ; l’édition Lite n’est pas prise en charge par cet installateur.

Sur le Pi, copier ces commandes dans la session SSH :

```sh
curl -fsSL https://raw.githubusercontent.com/sylvaingeinoz/OSC-HTTP-Show-emergency-message/main/install.sh -o install-stop-show.sh
bash install-stop-show.sh
sudo reboot
```

Le script demande le mot de passe `sudo`, installe les composants, sauvegarde les fichiers système modifiés et active le démarrage automatique. Il est prévu pour **un Pi dédié à l’afficheur**. Il conserve les réglages et la clé lorsqu’il est relancé pour une mise à jour. Il ne modifie pas l’accès SSH. Le téléchargement et l’installation initiale nécessitent Internet ; l’exploitation fonctionne ensuite sur le réseau local.

Après le redémarrage :

1. Ouvrir `http://stopshow.local:8080` depuis la régie (remplacer `stopshow` par le nom choisi ou l’IP du Pi).
2. Lire la clé en SSH avec `cat ~/.local/share/stop-show/data/token`, puis la saisir dans la page.
3. Envoyer la mire, vérifier le téléviseur, puis envoyer une consigne.

Le noir initial est normal : aucune consigne n’est affichée au démarrage.

### Installation depuis une copie Git

```sh
git clone https://github.com/sylvaingeinoz/OSC-HTTP-Show-emergency-message.git
cd OSC-HTTP-Show-emergency-message
bash install.sh
sudo reboot
```

## Fonctions

- Grandes consignes : changement de micro, reprise, **STOP SHOW rouge clignotant**.
- Prompteur fixe multiligne, choix de police et de taille, texte ajusté à l’écran.
- Heure, minuterie et compte à rebours vers une date/heure cible, dont minuit au Nouvel An.
- Retour au noir configurable : **15 secondes par défaut**, réarmé par chaque nouvelle consigne. **STOP SHOW suit exactement ce même délai**, sans verrouillage.
- Témoin discret optionnel restant visible au noir ; mire de préparation.
- Résolution, fréquence, rotation 90°/180°/270° et miroirs via les modes réellement annoncés par la TV ; essai de 20 secondes avec retour arrière sans confirmation.
- HTTP TCP 8080 et OSC UDP 9000, commandes protégées par une clé.

L’heure, les compteurs et la mire suivent également le délai au noir. La commande `keepalive` prolonge la consigne visible sans redémarrer le compteur. [Exemples Companion](COMPANION.md).

## Documentation et essais

- [Guide complet : installation, utilisation et dépannage](GUIDE.md)
- [Commandes HTTP et OSC pour Companion](COMPANION.md)
- [Démarrage propre, récupération et limites matérielles](DEMARRAGE.md)
- [Validation locale et recette sur le Pi](VALIDATION.md)

Pour essayer sur un ordinateur avec Python 3.9+ : `python3 server.py --data .data`, puis ouvrir `http://127.0.0.1:8080`. Les fonctions HDMI nécessitent le Pi sous Wayland.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

**Aucun démarrage matériel n’a encore été validé sur un Pi physique.** Le firmware et la TV peuvent afficher leurs propres logos ou messages avant la prise en charge par le système. Faire la recette matérielle avant utilisation en représentation. L’application conserve le signal HDMI au noir ; elle n’éteint pas la télévision.
