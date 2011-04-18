# -*- coding: utf-8 -*-
import path as path_mod
import msg as p
import os
import cfgparse2 as cfg
from helper_classes import Manifest, ManifestParser, SourceFile, IseProjectFile, VHDLFile, ModuleOptions

class Module(object):
    def __init__(self, url=None, files=None, manifest=None,
    path=None, isfetched=False, source=None, fetchto=None):
        self.options = ModuleOptions()
        if source == "local" and path != None:
            if not os.path.exists(path):
                raise ValueError("There is no such local module: " + path)

        if files == None:
            self.options["files"] = []
        elif not isinstance(files, list):
            self.options["files"] = [files]
        else:
            self.options["files"] = files
        if manifest != None and fetchto == None:
            options["fetchto"] = os.path.dirname(manifest.path)
        if manifest != None and url == None and path == None:
            self.options["url"] = os.path.dirname(manifest.path)
            self.options["path"] = os.path.dirname(manifest.path)
        else:
            if path != None and url == None:
                self.options["path"] = path
                self.options["url"] = path
            else:
                self.options["path"] = path
                self.options["url"] = url
        if manifest == None:
            if self.options["path"] != None:
                self.options["manifest"] = self.search_for_manifest()
            else:
                self.options["manifest"] = None
        else:
            self.options["manifest"] = manifest

        if source == "local":
            self.options["isfetched"] = True
        else:
            self.options["isfetched"] = isfetched
        if source != None:
            if source not in ["local", "svn", "git"]:
                raise ValueError("Inproper source: " + source)
            self.options["source"] = source
        else:
            self.options["source"] = "local"
        self.options["fetchto"] = fetchto

        self.options["isparsed"] = False
        basename = path_mod.url_basename(self.options["url"])
        if self.options["path"] != None:
            self.options["isfetched"] = True
        elif os.path.exists(os.path.join(self.options["fetchto"], basename)):
            self.options["isfetched"] = True
            self.path = os.path.join(self.options["fetchto"], basename)
        self.options["library"] = "work"
        self.parse_manifest()

    def __getattr__(self, attr):
        #options = object.__getattribute__(self, "options")
        return self.options[attr]

    def __str__(self):
        return self.url

    def search_for_manifest(self):
        """
        Look for manifest in the given folder
        """
        p.vprint("Looking for manifest in " + self.path)
        for filename in os.listdir(self.path):
            if filename == "manifest.py" and not os.path.isdir(filename):
                manifest = Manifest(path=os.path.abspath(os.path.join(self.path, filename)))
                return manifest
        # no manifest file found
        return None

    def make_list_(self, sth):
        if sth != None:
            if not isinstance(sth, (list,tuple)):
                sth = [sth]
        else:
            sth = []
        return sth

    def parse_manifest(self):
        if self.isparsed == True:
            return
        if self.isfetched == False:
            return

        manifest_parser = ManifestParser()
        if self.manifest == None:
            p.vprint(' '.join(["In module",str(self),"there is no manifest."]))
        else:
            manifest_parser.add_manifest(self.manifest)
            p.vprint("Parsing manifest file: " + str(self.manifest))

        opt_map = None
        try:
            opt_map = manifest_parser.parse()
        except NameError as ne:
            p.echo("Error while parsing {0}:\n{1}: {2}.".format(self.manifest, type(ne), ne))
            quit()
        if opt_map.root_module != None:
            root_path = path_mod.rel2abs(opt_map.root_module, self.path)
            self.root_module = Module(path=root_path, source="local", isfetched=True)
            self.root_module.parse_manifest()
            #if not os.path.exists(opt_map.root_manifest.path):
            #    p.echo("Error while parsing " + self.manifest + ". Root manifest doesn't exist: "
            #    + opt_map.root_manifest)
            #   quit()
        if opt_map.fetchto == None:
            self.fetchto = self.path
        else:
            if not path_mod.is_rel_path(opt_map.fetchto):
                p.echo(' '.join([os.path.basename(sys.argv[0]), "accepts relative paths only:", opt_map.fetchto]))
                quit()
            self.fetchto = path_mod.rel2abs(opt_map.fetchto, self.path)

        if self.ise == None:
            self.ise = "13.1"
        local_paths = self.make_list_(opt_map.local)
        local_mods = []
        for path in local_paths:
            path = path_mod.rel2abs(path, self.path)
            local_mods.append(Module(path=path, source="local"))
        self.local = local_mods

        if opt_map.files == None:
            directory = os.path.dirname(self.path)
            print "listing" + directory
            files = []
            for file in os.listdir(directory):
               path = os.path.join(directory, file)
               files.append(path)
            self.files = files
        else:
            files = []
            for path in opt_map.files:
                if not path_mod.is_abs_path(path):
                    files.append(path_mod.rel2abs(path, self.path))
                else:
                    p.echo(path + " is an absolute path. Omitting.")
            self.files = files

        opt_map.svn = self.make_list_(opt_map.svn)
        svn = []
        for url in opt_map.svn:
            svn.append(Module(url=url, source="svn", fetchto=self.fetchto))
        self.svn = svn

        opt_map.git = self.make_list_(opt_map.git)
        git = []
        for url in opt_map.git:
            git.append(Module(url=url, source="git", fetchto=self.fetchto))
        self.git = git

        self.vmap_opt = opt_map.vmap_opt
        self.vcom_opt = opt_map.vcom_opt
        self.vlog_opt = opt_map.vlog_opt

        self.isparsed = True
        self.library = opt_map.library
        if self.isfetched == True:
            self.make_list_of_files_()

    def is_fetched(self):
        return self.isfetched

    def fetch(self):
        if self.source == "local":
            self.path = self.url
        elif self.source == "svn":
            self.__fetch_from_svn(fetchto=fetchto)
        elif self.source == "git":
            self.__fetch_from_git(fetchto=fetchto)

        if self.isparsed != True:
            self.parse_manifest()
            self.make_list_of_files_()

        involved_modules = [self]
        modules_queue = [self]

        p.vprint("Fetching manifest: " + str(self.manifest))

        while len(modules_queue) > 0:
            cur_mod = modules_queue.pop()
            cur_mod.parse_manifest()
            print str(cur_mod)

            if cur_mod.root_module != None:
                root_module = cur_mod.root_module
                p.vprint("Encountered root manifest: " + str(root_module))
                new_modules = root_module.fetch()
                involved_modules.extend(new_modules)
                modules_queue.extend(new_modules)

            for i in cur_mod.local:
                p.vprint("Modules waiting in fetch queue:"+
                ' '.join([str(cur_mod.git), str(cur_mod.svn), str(cur_mod.local)]))

            for module in cur_mod.svn:
                p.vprint("Fetching to " + cur_mod.fetchto)
                path = module.__fetch_from_svn()
                module.path = path
                involved_modules.append(module)
                modules_queue.append(module)

            for module in cur_mod.git:
                p.vprint("Fetching to " + cur_mod.fetchto)
                path = module.__fetch_from_git()
                module.path = path
                involved_modules.append(module)
                modules_queue.append(module)

            for module in cur_mod.local:
                involved_modules.append(module)
                modules_queue.append(module)

            p.vprint("Modules scan queue: " + str(modules_queue))

        p.vprint("All found manifests have been scanned")
        return involved_modules

    def __fetch_from_svn(self):
        fetchto = self.fetchto
        if not os.path.exists(fetchto):
            os.mkdir(fetchto)

        cur_dir = os.getcwd()
        os.chdir(fetchto)
        p.echo(os.getcwd())
        basename = path_mod.url_basename(self.url)

        cmd = "svn checkout {0} {1}"
        cmd = cmd.format(self.url, basename)
      

        p.vprint(cmd)
        os.system(cmd)
        os.chdir(cur_dir)
        self.isfetched = True
        return os.path.join(fetchto, basename)

    def __fetch_from_git(self):
        fetchto = self.fetchto
        if not os.path.exists(fetchto):
            os.mkdir(fetchto)

        cur_dir = os.getcwd()
        os.chdir(fetchto)

        basename = url_basename(self.url)
        if basename.endswith(".git"):
            basename = basename[:-4] #remove trailing .git

        cmd = "git clone " + self.url
        p.vprint(cmd)
        os.system(cmd)
        #if revision:
        #    os.chdir(basename)
        #    os.system("git checkout " + revision)
        os.chdir(cur_dir)
        self.isfetched = True
        return os.path.join(fetchto, basename)

    def make_list_of_modules(self):
        p.vprint("Making list of modules for " + str(self))
        new_modules = [self]
        modules = [self]
        while len(new_modules) > 0:
            cur_module = new_modules.pop()
            if not cur_module.isfetched:
                p.echo("Error in modules list - unfetched module: " + cur_mod)
                quit()
            if cur_module.manifest == None:
                p.vprint("No manifest in " + str(cur_module))
                continue
            cur_module.parse_manifest()
            if cur_module.root_module != None:
                root_module = cur_module.root_module
                modules_from_root = root_module.make_list_of_modules()
                modules.extend(modules_from_root)

            for module in cur_module.local:
                modules.append(module)
                new_modules.append(module)

            for module in cur_module.git:
                modules.append(module)
                new_modules.append(module)

            for module in cur_module.svn:
                modules.append(module)
                new_modules.append(module)

        if len(modules) == 0:
            p.vprint("No modules were found in " + self.fetchto)
        return modules

    def make_list_of_files_(self, file_type = None, ret_class = SourceFile):
        def get_files_(path, file_type = None, ret_class = SourceFile):
            """
            Get lists of normal files and list folders recursively
            """
            ret = []
            for filename in os.listdir(path):
                if filename[0] == ".": #a hidden file/catalogue -> skip
                    continue
                if os.path.isdir(os.path.join(path, filename)):
                    ret.extend(get_files_(os.path.join(path, filename), file_type))
                else:
                    if file_type == None:
                        ret.append(ret_class(path=os.path.abspath(os.path.join(path, filename))))
                    else:
                        tmp = filename.rsplit('.')
                        ext = tmp[len(tmp)-1]
                        if ext == file_type:
                            ret.append( ret_class(path=os.path.abspath(os.path.join(path, filename))) )
            return ret

        files = []

        if self.manifest != None:
            if self.files != []:
                for file in self.files:
                    if os.path.isdir(file):
                        files.extend(get_files_(path=file, file_type=file_type, ret_class=ret_class))
                    else:
                        files.append(ret_class(file))
            else:
               files.extend(get_files_(path=self.path, file_type=file_type, ret_class=ret_class))
        else:
            files = get_files_(path=self.path, file_type=file_type, ret_class=ret_class)
        for file in files:
            file.library = self.library
        self.files = files

    def generate_deps_for_vhdl_in_modules(self):
        modules = self.make_list_of_modules()
        p.vprint("Using following modules for dependencies:" + str([str(i) for i in modules]))

        from copy import copy #shallow object copying
        all_files = [copy(f) for module in modules for f in module.files if f.extension() =="vhd"]
        p.vprint("All vhdl files:")
        for file in all_files:
            p.vprint(str(file) + ':' + file.library)
        for file in all_files:
            file.search_for_package()
            file.search_for_use()

        package_file_dict = {}
        for file in all_files:
            packages = file.package #look for package definitions
            if len(packages) != 0: #if there are some packages in the file
                for package in packages:
                    if package in package_file_dict:
                        p.echo("There might be a problem... Compilation unit " + package +
                        " has several instances:\n\t" + str(file) + "\n\t" + str(package_file_dict[package]))
                        package_file_dict[package.lower()] = [package_file_dict[package.lower()], file]#///////////////////////////////////////////////////
                    package_file_dict[package.lower()] = file #map found package to scanned file
            file_purename = os.path.splitext(file.name)[0]
            if file_purename in package_file_dict and package_file_dict[file_purename.lower()] != file:
                p.echo("There might be a problem... Compilation unit " + file_purename +
                    " has several instances:\n\t" + str(file) + "\n\t" + str(package_file_dict[file_purename]))
            package_file_dict[file_purename.lower()] = file

        p.vpprint(package_file_dict)

        file_file_dict = {}
        for file in all_files:
            for unit in file.use:
                if unit[1].lower() in package_file_dict:
                    if unit[0].lower() == package_file_dict[unit[1].lower()].library:
                        if file in file_file_dict:
                            file_file_dict[file].append(package_file_dict[unit[1].lower()])
                        else:
                            file_file_dict[file] = [package_file_dict[unit[1].lower()]]
                else:
                    p.echo("Cannot resolve dependency: " + str(file) + " depends on "
                        +"compilation unit " + str(unit) + ", which cannot be found")
        for file in all_files:
            if file not in file_file_dict:
                file_file_dict[file] = []
        p.vpprint(file_file_dict)
        return file_file_dict
