============
Installation
============

Plugins repository
------------------

*QBeach* is not yet available through the official *QGIS* plugins repository. Ideally, with some further debugging and documentation it should be submitted for consideration in the near future.

Install from zip
----------------

The quickest way to get up and running is probably to install the plugin from a zipped file:

* Go to the `Github repository <https://github.com/JTMelly/QBeach>`_
* Download the zipped repository (green "code" button in upper right corner)
* Launch *QGIS*
* Use *Plugins > Manage and Install Plugins... > Install from ZIP*
* Select the zipped download and choose "Install Plugin"

Experimental plugins directory
------------------------------

If you want to keep experimental plugins separate from regularly-installed *QGIS* plugins, create a directory, clone the repository to that directory, and point the *QGIS* plugins directory to the new directory using a symlink.

.. code-block:: bash

   # clone the repository
   mkdir qbeach
   cd qbeach
   git clone https://github.com/JTMelly/QBeach.git

.. code-block:: bash

   # find the QGIS plugins directory and point it to the cloned repo
   ln -s /path/to/qbeach /path/to/qgis/plugins