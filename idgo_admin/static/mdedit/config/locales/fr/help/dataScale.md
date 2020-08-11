<!-- Begin @dataScaleDistance.md -->

# Résolution spatiale

## Définition

Ce champ permet de spécifier l’échelle ou la résolution de la donnée.
Il s’agit généralement de l’échelle optimum d’utilisation de la donnée pour réaliser des cartes ou des analyses spatiales.

On choisit d’indiquer la résolution spatiale :
soit en échelle de représentation ou échelle équivalente (principalement pour les représentations cartographiques),
soit sous la forme d’une distance au sol, principalement pour les données maillées et des produits dérivés d’imagerie, représentant la résolution des données (typiquement la taille d’un pixel d’une image au sol).

## Recommandations

L’échelle de la donnée décrite ne peut pas être plus grande que celle du référentiel utilisé pour produire cette donnée géographique. Par exemple, on ne produit pas une donnée au 1 :2000ème  avec un SCAN 25).

Pour l’échelle de représentation, indiquer seulement le dénominateur : pour une échelle au 1 :10000ème, la valeur à renseigner est « 10000 ».
Pour la résolution, la valeur doit être renseignée en mètre.

Un complément d’information concernant la résolution spatiale et notamment la précision de positionnement altimétrique et planimétrique de la donnée peut être indiqué dans le champ relatif à la qualité (cf. paragraphe #.
    
## Exemples

Echelle : « 10000 »
Résolution : « 0.5 »

<!-- End @dataScaleDistance.md -->
