<!-- Begin @dataIdentifiers.md -->

# Identifiant de la donnée

## Définition

Le ou les identifiants de la donnée correspondent à un ou plusieurs codes permettant d’identifier de manière unique la donnée.  
Ces codes ne sont jamais modifiés pour une donnée même lors de sa mise à jour.

## Recommandations

Afin d’obtenir un code unique, il est recommandé de construire cet identifiant en associant le code pays de l’organisme propriétaire de la donnée, son numéro SIREN, ainsi qu’un code unique définit par le propriétaire de la donnée selon le schéma ci-dessous.  
Le code unique peut être généré de façon automatique selon un algorithme ou de façon aléatoire.

Structure recommandée de l’identifiant :

- Code du pays : « FR »
- Séparateur : « – »
- Code SIREN : code à 9 chiffres
- Séparateur : « – »
- Code unique

Il est également possible d’associer au code un espace de nommage pour préciser sa provenance (cf. exemple 2 ci-dessous). L’espace de nommage correspond au domaine dans lequel la donnée est identifiée par ce code et renvoie généralement à l’organisme qui a attribué l’identifiant à la donnée.  
Il est recommandé d’intégrer les informations concernant l’espace de nom, dans le code de la donnée (cf. exemple 1 ci-dessous).

## Exemples

**Identifiant de la donnée :**

- Code : « FR–2467800019–150523_D004 »

Ce qui signifie :

- FR : code pour la France
- 2467800019 : numéro SIREN de la Région Alsace
- 150223_R004 : numéro unique établi en interne à la Région Alsace, composé de la date de création de la donnée (23/0#12) suivi de la lettre « D » indiquant qu’il s’agit d’une donnée et d’un numéro d’ordre.

**Identifiant de la donnée :**

- Code : « 110805-BdOCS2008-CIGAL »
- Espace de nommage : « FR–#00019 »

Ce qui signifie :

- Pour le code : « 110805-BdOCS2008-CIGAL » est un code unique établi en interne à la Région Alsace pour le partenariat CIGAL, composé de la date de création de la donnée (09/0#11) suivi du nom officiel de la base de données
- Pour l’espace de nommage : « FR » est le code pour la France et « #00019 », le numéro SIREN de la Région Alsace

<!-- End @dataIdentifiers.md -->
